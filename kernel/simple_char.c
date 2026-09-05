// SPDX-License-Identifier: MIT
/*
 * simple_char.c - a small, bounded, mutex-protected character device.
 *
 * The optional GPIO and I2C paths are deliberately opt-in module parameters.
 * They are intended as auditable Raspberry Pi integration hooks, not as a
 * board-specific driver or a replacement for a Device Tree binding.
 */

#include <linux/atomic.h>
#include <linux/build_bug.h>
#include <linux/capability.h>
#include <linux/cdev.h>
#include <linux/compat.h>
#include <linux/device.h>
#include <linux/err.h>
#include <linux/fs.h>
#include <linux/gpio.h>
#include <linux/gpio/consumer.h>
#include <linux/i2c.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include <linux/version.h>

#include "simple_char_ioctl.h"

#define SIMPLE_CHAR_MIN_BUFFER_SIZE 64U
#define SIMPLE_CHAR_MAX_BUFFER_SIZE (1024U * 1024U)
#define SIMPLE_CHAR_DEFAULT_BUFFER_SIZE 4096U

struct simple_char_device {
	dev_t devt;
	struct cdev cdev;
	struct class *class;
	struct device *device;

	char *buffer;
	size_t capacity;
	size_t data_len;
	struct mutex lock;

	atomic_t open_handles;
	atomic_t last_error;
	atomic64_t open_count;
	atomic64_t read_ops;
	atomic64_t write_ops;
	atomic64_t bytes_read;
	atomic64_t bytes_written;

	struct gpio_desc *gpio_desc;
	bool gpio_requested;
	u32 gpio_value;
	struct i2c_client *i2c_client;
};

static struct simple_char_device *simple_char;

static unsigned int buffer_size = SIMPLE_CHAR_DEFAULT_BUFFER_SIZE;
module_param(buffer_size, uint, 0444);
MODULE_PARM_DESC(buffer_size, "In-memory device capacity (64..1048576 bytes)");

static bool enable_gpio;
module_param(enable_gpio, bool, 0444);
MODULE_PARM_DESC(enable_gpio, "Enable the optional GPIO hook (default: false)");

static int gpio_num = -1;
module_param(gpio_num, int, 0444);
MODULE_PARM_DESC(gpio_num, "Legacy global GPIO number; required when enable_gpio=1");

static bool gpio_active_low;
module_param(gpio_active_low, bool, 0444);
MODULE_PARM_DESC(gpio_active_low, "Invert logical GPIO output values");

static bool enable_i2c;
module_param(enable_i2c, bool, 0444);
MODULE_PARM_DESC(enable_i2c, "Enable the optional I2C register-write hook (default: false)");

static int i2c_bus = -1;
module_param(i2c_bus, int, 0444);
MODULE_PARM_DESC(i2c_bus, "I2C adapter number; required when enable_i2c=1");

static int i2c_addr;
module_param(i2c_addr, int, 0444);
MODULE_PARM_DESC(i2c_addr, "7-bit I2C address; required when enable_i2c=1");

static long simple_char_fail(struct simple_char_device *dev, long error)
{
	if (error < 0)
		atomic_set(&dev->last_error, (int)error);
	return error;
}

static int simple_char_open(struct inode *inode, struct file *file)
{
	struct simple_char_device *dev;

	dev = container_of(inode->i_cdev, struct simple_char_device, cdev);
	file->private_data = dev;
	/* Serialize VFS position updates when dup()/fork() shares this file. */
	file->f_mode |= FMODE_ATOMIC_POS;
	atomic_inc(&dev->open_handles);
	atomic64_inc(&dev->open_count);

	return 0;
}

static int simple_char_release(struct inode *inode, struct file *file)
{
	struct simple_char_device *dev = file->private_data;

	(void)inode;
	atomic_dec(&dev->open_handles);
	return 0;
}

static ssize_t simple_char_read(struct file *file, char __user *destination,
				size_t count, loff_t *position)
{
	struct simple_char_device *dev = file->private_data;
	size_t available;
	size_t requested;
	size_t copied;
	unsigned long not_copied;
	int error;

	if (count == 0)
		return 0;

	error = mutex_lock_interruptible(&dev->lock);
	if (error)
		return simple_char_fail(dev, error);

	if (*position < 0) {
		error = -EINVAL;
		goto out_error;
	}

	/* Compare before narrowing loff_t on 32-bit kernels (including pread). */
	if (*position >= (loff_t)dev->data_len) {
		mutex_unlock(&dev->lock);
		return 0;
	}

	available = dev->data_len - (size_t)*position;
	requested = min(count, available);
	not_copied = copy_to_user(destination, dev->buffer + *position, requested);
	copied = requested - not_copied;

	if (copied > 0) {
		*position += copied;
		atomic64_inc(&dev->read_ops);
		atomic64_add(copied, &dev->bytes_read);
	}

	if (not_copied > 0)
		atomic_set(&dev->last_error, -EFAULT);

	mutex_unlock(&dev->lock);
	return copied > 0 ? (ssize_t)copied : -EFAULT;

out_error:
	mutex_unlock(&dev->lock);
	return simple_char_fail(dev, error);
}

static ssize_t simple_char_write(struct file *file, const char __user *source,
				 size_t count, loff_t *position)
{
	struct simple_char_device *dev = file->private_data;
	char *temporary;
	size_t available;
	size_t requested;
	size_t copied;
	unsigned long not_copied;
	int error;

	if (count == 0)
		return 0;

	error = mutex_lock_interruptible(&dev->lock);
	if (error)
		return simple_char_fail(dev, error);

	if (*position < 0) {
		error = -EINVAL;
		goto out_error;
	}

	if (*position >= (loff_t)dev->capacity) {
		error = -ENOSPC;
		goto out_error;
	}

	available = dev->capacity - (size_t)*position;
	requested = min(count, available);
	/* copy_from_user zero-fills an uncopied tail; never do that to live data. */
	temporary = kvmalloc(requested, GFP_KERNEL);
	if (!temporary) {
		error = -ENOMEM;
		goto out_error;
	}
	not_copied = copy_from_user(temporary, source, requested);
	copied = requested - not_copied;

	if (copied > 0) {
		memcpy(dev->buffer + *position, temporary, copied);
		*position += copied;
		dev->data_len = max(dev->data_len, (size_t)*position);
		atomic64_inc(&dev->write_ops);
		atomic64_add(copied, &dev->bytes_written);
	}

	if (not_copied > 0)
		atomic_set(&dev->last_error, -EFAULT);
	else if (requested < count)
		atomic_set(&dev->last_error, -ENOSPC);

	memzero_explicit(temporary, requested);
	kvfree(temporary);
	mutex_unlock(&dev->lock);
	return copied > 0 ? (ssize_t)copied : -EFAULT;

out_error:
	mutex_unlock(&dev->lock);
	return simple_char_fail(dev, error);
}

static loff_t simple_char_llseek(struct file *file, loff_t offset, int whence)
{
	struct simple_char_device *dev = file->private_data;
	loff_t result;
	int error;

	error = mutex_lock_interruptible(&dev->lock);
	if (error)
		return simple_char_fail(dev, error);
	result = fixed_size_llseek(file, offset, whence, dev->capacity);
	if (result < 0)
		simple_char_fail(dev, result);
	mutex_unlock(&dev->lock);
	return result;
}

static long simple_char_get_stats(struct simple_char_device *dev,
				  unsigned long argument)
{
	struct simple_char_stats stats = { 0 };
	int error;

	error = mutex_lock_interruptible(&dev->lock);
	if (error)
		return simple_char_fail(dev, error);
	/* Sample related I/O totals and size under the same lock as their updates. */
	stats.open_count = atomic64_read(&dev->open_count);
	stats.read_ops = atomic64_read(&dev->read_ops);
	stats.write_ops = atomic64_read(&dev->write_ops);
	stats.bytes_read = atomic64_read(&dev->bytes_read);
	stats.bytes_written = atomic64_read(&dev->bytes_written);
	stats.capacity = dev->capacity;
	stats.open_handles = atomic_read(&dev->open_handles);
	stats.last_error = atomic_read(&dev->last_error);
	stats.gpio_enabled = enable_gpio;
	stats.i2c_enabled = enable_i2c;

	stats.data_size = dev->data_len;
	stats.gpio_value = dev->gpio_value;
	mutex_unlock(&dev->lock);

	if (copy_to_user((void __user *)argument, &stats, sizeof(stats)))
		return simple_char_fail(dev, -EFAULT);
	return 0;
}

static long simple_char_clear(struct file *file,
			      struct simple_char_device *dev)
{
	int error;

	if (!(file->f_mode & FMODE_WRITE))
		return simple_char_fail(dev, -EBADF);

	/* Match the VFS lock order: file position, then device state. */
	error = mutex_lock_interruptible(&file->f_pos_lock);
	if (error)
		return simple_char_fail(dev, error);
	error = mutex_lock_interruptible(&dev->lock);
	if (error) {
		mutex_unlock(&file->f_pos_lock);
		return simple_char_fail(dev, error);
	}
	memset(dev->buffer, 0, dev->capacity);
	dev->data_len = 0;
	file->f_pos = 0;
	mutex_unlock(&dev->lock);
	mutex_unlock(&file->f_pos_lock);
	return 0;
}

static long simple_char_gpio_set(struct file *file,
				 struct simple_char_device *dev,
				 unsigned long argument)
{
	struct simple_char_gpio_request request;
	int physical_value;
	int error;

	if (!(file->f_mode & FMODE_WRITE))
		return simple_char_fail(dev, -EBADF);
	if (!enable_gpio || !dev->gpio_requested)
		return simple_char_fail(dev, -EOPNOTSUPP);
	if (!capable(CAP_SYS_RAWIO))
		return simple_char_fail(dev, -EPERM);
	if (copy_from_user(&request, (void __user *)argument, sizeof(request)))
		return simple_char_fail(dev, -EFAULT);
	if (request.value > 1)
		return simple_char_fail(dev, -EINVAL);

	error = mutex_lock_interruptible(&dev->lock);
	if (error)
		return simple_char_fail(dev, error);
	physical_value = gpio_active_low ? !request.value : request.value;
	gpiod_set_raw_value_cansleep(dev->gpio_desc, physical_value);
	dev->gpio_value = request.value;
	mutex_unlock(&dev->lock);

	return 0;
}

static long simple_char_i2c_write(struct file *file,
				  struct simple_char_device *dev,
				  unsigned long argument)
{
	struct simple_char_i2c_request request;
	int error;

	if (!(file->f_mode & FMODE_WRITE))
		return simple_char_fail(dev, -EBADF);
	if (!enable_i2c || !dev->i2c_client)
		return simple_char_fail(dev, -EOPNOTSUPP);
	if (!capable(CAP_SYS_RAWIO))
		return simple_char_fail(dev, -EPERM);
	if (copy_from_user(&request, (void __user *)argument, sizeof(request)))
		return simple_char_fail(dev, -EFAULT);
	if (request.reg > 0xffU || request.value > 0xffU)
		return simple_char_fail(dev, -EINVAL);

	error = mutex_lock_interruptible(&dev->lock);
	if (error)
		return simple_char_fail(dev, error);
#if IS_ENABLED(CONFIG_I2C)
	error = i2c_smbus_write_byte_data(dev->i2c_client, (u8)request.reg,
					  (u8)request.value);
#else
	error = -EOPNOTSUPP;
#endif
	mutex_unlock(&dev->lock);

	if (error < 0)
		return simple_char_fail(dev, error);
	return 0;
}

static long simple_char_ioctl(struct file *file, unsigned int command,
			      unsigned long argument)
{
	struct simple_char_device *dev = file->private_data;

	if (_IOC_TYPE(command) != SIMPLE_CHAR_IOC_MAGIC ||
	    _IOC_NR(command) > SIMPLE_CHAR_IOC_MAX_NR)
		return simple_char_fail(dev, -ENOTTY);

	switch (command) {
	case SIMPLE_CHAR_IOC_GET_STATS:
		return simple_char_get_stats(dev, argument);
	case SIMPLE_CHAR_IOC_CLEAR:
		return simple_char_clear(file, dev);
	case SIMPLE_CHAR_IOC_GPIO_SET:
		return simple_char_gpio_set(file, dev, argument);
	case SIMPLE_CHAR_IOC_I2C_WRITE_REG:
		return simple_char_i2c_write(file, dev, argument);
	default:
		return simple_char_fail(dev, -ENOTTY);
	}
}

static const struct file_operations simple_char_fops = {
	.owner = THIS_MODULE,
	.open = simple_char_open,
	.release = simple_char_release,
	.read = simple_char_read,
	.write = simple_char_write,
	.llseek = simple_char_llseek,
	.unlocked_ioctl = simple_char_ioctl,
#ifdef CONFIG_COMPAT
	.compat_ioctl = compat_ptr_ioctl,
#endif
};

static int simple_char_gpio_init(struct simple_char_device *dev)
{
	unsigned long request_flags;
	int physical_value;
	int error;

	if (!enable_gpio)
		return 0;
	if (!IS_ENABLED(CONFIG_GPIOLIB))
		return -EOPNOTSUPP;
	if (!gpio_is_valid(gpio_num))
		return -EINVAL;

	physical_value = gpio_active_low ? 1 : 0;
	request_flags = physical_value ? GPIOF_OUT_INIT_HIGH : GPIOF_OUT_INIT_LOW;
	error = gpio_request_one(gpio_num, request_flags,
				 SIMPLE_CHAR_DEVICE_NAME);
	if (error)
		return error;
	dev->gpio_requested = true;

	/* gpio_to_desc() is valid after acquiring the line with gpio_request_one(). */
	dev->gpio_desc = gpio_to_desc(gpio_num);
	if (!dev->gpio_desc) {
		gpio_free(gpio_num);
		dev->gpio_requested = false;
		return -ENODEV;
	}
	dev->gpio_value = 0;

	return 0;
}

static void simple_char_gpio_cleanup(struct simple_char_device *dev)
{
	int physical_value;

	if (!dev->gpio_requested)
		return;
	physical_value = gpio_active_low ? 1 : 0;
	gpiod_set_raw_value_cansleep(dev->gpio_desc, physical_value);
	gpio_free(gpio_num);
	dev->gpio_desc = NULL;
	dev->gpio_requested = false;
}

static int simple_char_i2c_init(struct simple_char_device *dev)
{
#if IS_ENABLED(CONFIG_I2C)
	struct i2c_adapter *adapter;

	if (!enable_i2c)
		return 0;
	if (i2c_bus < 0 || i2c_addr < 0x03 || i2c_addr > 0x77)
		return -EINVAL;

	adapter = i2c_get_adapter(i2c_bus);
	if (!adapter)
		return -ENODEV;
	if (!i2c_check_functionality(adapter, I2C_FUNC_SMBUS_WRITE_BYTE_DATA)) {
		i2c_put_adapter(adapter);
		return -EOPNOTSUPP;
	}

	dev->i2c_client = i2c_new_dummy_device(adapter, i2c_addr);
	i2c_put_adapter(adapter);
	if (IS_ERR(dev->i2c_client)) {
		int error = PTR_ERR(dev->i2c_client);

		dev->i2c_client = NULL;
		return error;
	}

	return 0;
#else
	(void)dev;
	return enable_i2c ? -EOPNOTSUPP : 0;
#endif
}

static void simple_char_i2c_cleanup(struct simple_char_device *dev)
{
#if IS_ENABLED(CONFIG_I2C)
	if (!dev->i2c_client)
		return;
	i2c_unregister_device(dev->i2c_client);
	dev->i2c_client = NULL;
#else
	(void)dev;
#endif
}

static int __init simple_char_init(void)
{
	struct simple_char_device *dev;
	int error;

	BUILD_BUG_ON(sizeof(struct simple_char_stats) != 72);

	if (buffer_size < SIMPLE_CHAR_MIN_BUFFER_SIZE ||
	    buffer_size > SIMPLE_CHAR_MAX_BUFFER_SIZE)
		return -EINVAL;

	dev = kzalloc(sizeof(*dev), GFP_KERNEL);
	if (!dev)
		return -ENOMEM;

	dev->buffer = kvzalloc(buffer_size, GFP_KERNEL);
	if (!dev->buffer) {
		error = -ENOMEM;
		goto error_free_device;
	}
	dev->capacity = buffer_size;
	mutex_init(&dev->lock);
	atomic_set(&dev->open_handles, 0);
	atomic_set(&dev->last_error, 0);
	atomic64_set(&dev->open_count, 0);
	atomic64_set(&dev->read_ops, 0);
	atomic64_set(&dev->write_ops, 0);
	atomic64_set(&dev->bytes_read, 0);
	atomic64_set(&dev->bytes_written, 0);

	error = simple_char_gpio_init(dev);
	if (error)
		goto error_free_buffer;

	error = simple_char_i2c_init(dev);
	if (error)
		goto error_cleanup_gpio;

	error = alloc_chrdev_region(&dev->devt, 0, 1, SIMPLE_CHAR_DEVICE_NAME);
	if (error)
		goto error_cleanup_i2c;

#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 4, 0)
	dev->class = class_create(SIMPLE_CHAR_DEVICE_NAME);
#else
	dev->class = class_create(THIS_MODULE, SIMPLE_CHAR_DEVICE_NAME);
#endif
	if (IS_ERR(dev->class)) {
		error = PTR_ERR(dev->class);
		dev->class = NULL;
		goto error_unregister_region;
	}

	dev->device = device_create(dev->class, NULL, dev->devt, NULL,
				    SIMPLE_CHAR_DEVICE_NAME);
	if (IS_ERR(dev->device)) {
		error = PTR_ERR(dev->device);
		dev->device = NULL;
		goto error_destroy_class;
	}

	/* Publish callbacks last: no fallible work may follow successful cdev_add. */
	cdev_init(&dev->cdev, &simple_char_fops);
	dev->cdev.owner = THIS_MODULE;
	error = cdev_add(&dev->cdev, dev->devt, 1);
	if (error) {
		kobject_put(&dev->cdev.kobj);
		goto error_destroy_device;
	}

	simple_char = dev;
	pr_info("simple_char: loaded major=%u minor=%u capacity=%zu gpio=%d i2c=%d\n",
		MAJOR(dev->devt), MINOR(dev->devt), dev->capacity,
		enable_gpio, enable_i2c);
	return 0;

error_destroy_device:
	device_destroy(dev->class, dev->devt);
error_destroy_class:
	class_destroy(dev->class);
error_unregister_region:
	unregister_chrdev_region(dev->devt, 1);
error_cleanup_i2c:
	simple_char_i2c_cleanup(dev);
error_cleanup_gpio:
	simple_char_gpio_cleanup(dev);
error_free_buffer:
	kvfree(dev->buffer);
error_free_device:
	kfree(dev);
	pr_err("simple_char: initialization failed: %d\n", error);
	return error;
}

static void __exit simple_char_exit(void)
{
	struct simple_char_device *dev = simple_char;

	if (!dev)
		return;

	cdev_del(&dev->cdev);
	device_destroy(dev->class, dev->devt);
	class_destroy(dev->class);
	unregister_chrdev_region(dev->devt, 1);
	simple_char_i2c_cleanup(dev);
	simple_char_gpio_cleanup(dev);
	memzero_explicit(dev->buffer, dev->capacity);
	kvfree(dev->buffer);
	kfree(dev);
	simple_char = NULL;
	pr_info("simple_char: unloaded\n");
}

module_init(simple_char_init);
module_exit(simple_char_exit);

MODULE_AUTHOR("Rohit Patel");
MODULE_DESCRIPTION("Mutex-protected character device with opt-in GPIO/I2C hooks");
MODULE_LICENSE("Dual MIT/GPL");
MODULE_VERSION("1.0.0");

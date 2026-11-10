// SPDX-License-Identifier: MIT
/* Five RMTFS libudev APIs, with /sys supplied by a read-only synthetic fixture. */
#include <libudev.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/sysmacros.h>

static const char *scenario;
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"FAIL %s:%d: %s\n",scenario,__LINE__,#x); exit(1); } } while (0)
int main(int argc,char **argv)
{
    CHECK(argc==2);scenario=argv[1];
    unsigned count=!strcmp(scenario,"repeat") ? 32 : 1;
    for(unsigned i=0;i<count;i++) {
        struct udev *ctx=udev_new();CHECK(ctx);
        struct udev_device *dev=udev_device_new_from_devnum(ctx,'c',makedev(240,!strcmp(scenario,"missing-device") ? 2 : 1));
        if(!strcmp(scenario,"missing-device")) CHECK(!dev);
        else {
            CHECK(dev);
            const char *address=udev_device_get_sysattr_value(dev,"phys_addr");
            const char *size=udev_device_get_sysattr_value(dev,"size");
            CHECK(address && size && strtoull(address,NULL,16)==UINT64_C(0x0fd80000) && strtoull(size,NULL,16)==UINT64_C(0x180000));
            if(!strcmp(scenario,"cached-attributes")) {
                CHECK(udev_device_get_sysattr_value(dev,"phys_addr")==address);
                CHECK(udev_device_get_sysattr_value(dev,"size")==size);
            } else if(!strcmp(scenario,"missing-attribute")) CHECK(!udev_device_get_sysattr_value(dev,"absent_attribute"));
            else CHECK(!strcmp(scenario,"attributes") || !strcmp(scenario,"repeat"));
            CHECK(!udev_device_unref(dev));
        }
        CHECK(!udev_unref(ctx));
    }
    printf("LIBUDEV_RMTFS_CASE_PASS %s\n",scenario);return 0;
}

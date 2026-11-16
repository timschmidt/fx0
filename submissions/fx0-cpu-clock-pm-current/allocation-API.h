/* Fixture allocation services retain their existing failure injection. */
#define devm_kzalloc_obj(dev,object) devm_kzalloc((dev),sizeof(object),GFP_KERNEL)
#define devm_kzalloc_objs(dev,object,count) devm_kcalloc((dev),(count),sizeof(object),GFP_KERNEL)
#define devm_kzalloc_flex(dev,object,member,count) devm_kzalloc((dev),sizeof(object)+sizeof((object).member[0])*(count),GFP_KERNEL)

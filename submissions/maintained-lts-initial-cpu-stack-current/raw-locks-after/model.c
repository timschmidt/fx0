
#include <stdbool.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
static int checks, failures, cases;
#define CHECK(x) do { checks++; if (!(x)) { failures++; if(failures<9)fprintf(stderr,"line%d: %s\n",__LINE__,#x); } } while(0)
#define ENXIO 6
#define HWLOCK_IRQSTATE 2
#define HWLOCK_IRQ 1
#define __acquires(x)
#define __releases(x)
struct lock { int initialized; };
struct regmap {
 void (*lock)(void *), (*unlock)(void *); void *lock_arg, *lock_key;
 bool can_sleep; struct lock raw_spinlock,spinlock,mutex;
 unsigned long raw_spinlock_flags,spinlock_flags; void *hwlock;
};
struct regmap_config {
 const char *name; unsigned int reg_bits,val_bits,reg_stride,max_register;
 bool fast_io,use_raw_spinlock,disable_locking,can_sleep,use_hwlock;
 void (*lock)(void *),(*unlock)(void *); void *lock_arg;
 unsigned int hwlock_id,hwlock_mode; const void *rd_table,*wr_table;
};
struct regmap_bus { bool fast_io; };
static const int spm_8226_l2_read_table,spm_8226_l2_write_table;
static int rt,in_ipi,invalid_wait,raw_locks,raw_unlocks,spin_locks,spin_unlocks,mutex_locks,mutex_unlocks;
static int hw_locks,hw_unlocks,custom_locks,custom_unlocks,no_hw;
#define raw_spin_lock_init(p) ((p)->initialized=1)
#define spin_lock_init(p) ((p)->initialized=1)
#define mutex_init(p) ((p)->initialized=1)
#define lockdep_set_class_and_name(p,key,name) do{CHECK((p)->initialized);(void)(key);(void)(name);}while(0)
#define raw_spin_lock_irqsave(p,flags) do{CHECK((p)->initialized);raw_locks++;flags=0x34;}while(0)
#define raw_spin_unlock_irqrestore(p,flags) do{CHECK((p)->initialized);CHECK((flags)==0x34);raw_unlocks++;}while(0)
#define spin_lock_irqsave(p,flags) do{CHECK((p)->initialized);spin_locks++;invalid_wait+=rt&&in_ipi;flags=0x12;}while(0)
#define spin_unlock_irqrestore(p,flags) do{CHECK((p)->initialized);CHECK((flags)==0x12);spin_unlocks++;}while(0)
static void mutex_lock(struct lock *p){CHECK(p->initialized);mutex_locks++;invalid_wait+=in_ipi;}
static void mutex_unlock(struct lock *p){CHECK(p->initialized);mutex_unlocks++;}
static void regmap_debugfs_disable(struct regmap *p){CHECK(p!=NULL);}
static void *hwspin_lock_request_specific(unsigned int id){CHECK(id==3);return no_hw?NULL:(void *)(uintptr_t)3;}
#define hwspin_lock_timeout(p,t) do{CHECK((p)!=NULL&&(t)==UINT_MAX);hw_locks++;}while(0)
#define hwspin_lock_timeout_irq(p,t) hwspin_lock_timeout(p,t)
#define hwspin_lock_timeout_irqsave(p,t,flags) do{hwspin_lock_timeout(p,t);*(flags)=0x12;}while(0)
#define hwspin_unlock(p) do{CHECK((p)!=NULL);hw_unlocks++;}while(0)
#define hwspin_unlock_irq(p) hwspin_unlock(p)
#define hwspin_unlock_irqrestore(p,flags) do{CHECK(*(flags)==0x12);hwspin_unlock(p);}while(0)
static const struct regmap_config spm_8226_l2_regmap_config = {
	.name = "l2-master",
	.reg_bits = 32,
	.val_bits = 32,
	.reg_stride = 4,
	.max_register = 0xffc,
	.fast_io = true,
	.use_raw_spinlock = true,
	.rd_table = &spm_8226_l2_read_table,
	.wr_table = &spm_8226_l2_write_table,
};
static const struct regmap_config saw_regmap_config = {
	.name = "saw",
	.reg_bits = 32,
	.val_bits = 32,
	.reg_stride = 4,
	.use_raw_spinlock = true,
};
static const struct regmap_config spmi_regmap_config = {
	.reg_bits	= 16,
	.val_bits	= 8,
	.max_register	= 0xffff,
	.fast_io	= true,
	.use_raw_spinlock = true,
};
static void regmap_lock_hwlock(void *__map)
{
	struct regmap *map = __map;

	hwspin_lock_timeout(map->hwlock, UINT_MAX);
}

static void regmap_lock_hwlock_irq(void *__map)
{
	struct regmap *map = __map;

	hwspin_lock_timeout_irq(map->hwlock, UINT_MAX);
}

static void regmap_lock_hwlock_irqsave(void *__map)
{
	struct regmap *map = __map;
	unsigned long flags = 0;

	hwspin_lock_timeout_irqsave(map->hwlock, UINT_MAX,
				    &flags);
	map->spinlock_flags = flags;
}

static void regmap_unlock_hwlock(void *__map)
{
	struct regmap *map = __map;

	hwspin_unlock(map->hwlock);
}

static void regmap_unlock_hwlock_irq(void *__map)
{
	struct regmap *map = __map;

	hwspin_unlock_irq(map->hwlock);
}

static void regmap_unlock_hwlock_irqrestore(void *__map)
{
	struct regmap *map = __map;

	hwspin_unlock_irqrestore(map->hwlock, &map->spinlock_flags);
}

static void regmap_lock_unlock_none(void *__map)
{

}

static void regmap_lock_mutex(void *__map)
{
	struct regmap *map = __map;
	mutex_lock(&map->mutex);
}

static void regmap_unlock_mutex(void *__map)
{
	struct regmap *map = __map;
	mutex_unlock(&map->mutex);
}

static void regmap_lock_spinlock(void *__map)
__acquires(&map->spinlock)
{
	struct regmap *map = __map;
	unsigned long flags;

	spin_lock_irqsave(&map->spinlock, flags);
	map->spinlock_flags = flags;
}

static void regmap_unlock_spinlock(void *__map)
__releases(&map->spinlock)
{
	struct regmap *map = __map;
	spin_unlock_irqrestore(&map->spinlock, map->spinlock_flags);
}

static void regmap_lock_raw_spinlock(void *__map)
__acquires(&map->raw_spinlock)
{
	struct regmap *map = __map;
	unsigned long flags;

	raw_spin_lock_irqsave(&map->raw_spinlock, flags);
	map->raw_spinlock_flags = flags;
}

static void regmap_unlock_raw_spinlock(void *__map)
__releases(&map->raw_spinlock)
{
	struct regmap *map = __map;
	raw_spin_unlock_irqrestore(&map->raw_spinlock, map->raw_spinlock_flags);
}


static int select_lock(struct regmap *map, const struct regmap_config *config,
                       const struct regmap_bus *bus)
{
 int ret=0; void *lock_key=NULL; const char *lock_name="actual-regmap";
	if (config->disable_locking) {
		map->lock = map->unlock = regmap_lock_unlock_none;
		map->can_sleep = config->can_sleep;
		regmap_debugfs_disable(map);
	} else if (config->lock && config->unlock) {
		map->lock = config->lock;
		map->unlock = config->unlock;
		map->lock_arg = config->lock_arg;
		map->can_sleep = config->can_sleep;
	} else if (config->use_hwlock) {
		map->hwlock = hwspin_lock_request_specific(config->hwlock_id);
		if (!map->hwlock) {
			ret = -ENXIO;
			goto err_name;
		}

		switch (config->hwlock_mode) {
		case HWLOCK_IRQSTATE:
			map->lock = regmap_lock_hwlock_irqsave;
			map->unlock = regmap_unlock_hwlock_irqrestore;
			break;
		case HWLOCK_IRQ:
			map->lock = regmap_lock_hwlock_irq;
			map->unlock = regmap_unlock_hwlock_irq;
			break;
		default:
			map->lock = regmap_lock_hwlock;
			map->unlock = regmap_unlock_hwlock;
			break;
		}

		map->lock_arg = map;
	} else {
		if ((bus && bus->fast_io) ||
		    config->fast_io) {
			if (config->use_raw_spinlock) {
				raw_spin_lock_init(&map->raw_spinlock);
				map->lock = regmap_lock_raw_spinlock;
				map->unlock = regmap_unlock_raw_spinlock;
				lockdep_set_class_and_name(&map->raw_spinlock,
							   lock_key, lock_name);
			} else {
				spin_lock_init(&map->spinlock);
				map->lock = regmap_lock_spinlock;
				map->unlock = regmap_unlock_spinlock;
				lockdep_set_class_and_name(&map->spinlock,
							   lock_key, lock_name);
			}
		} else {
			mutex_init(&map->mutex);
			map->lock = regmap_lock_mutex;
			map->unlock = regmap_unlock_mutex;
			map->can_sleep = true;
			lockdep_set_class_and_name(&map->mutex,
						   lock_key, lock_name);
		}
		map->lock_arg = map;
		map->lock_key = lock_key;
	}

 return 0;
err_name:
 return ret;
}

static void clear_trace(void){invalid_wait=raw_locks=raw_unlocks=spin_locks=spin_unlocks=mutex_locks=mutex_unlocks=hw_locks=hw_unlocks=custom_locks=custom_unlocks=no_hw=0;}
static void custom_lock(void *p){CHECK(p==(void *)(uintptr_t)9);custom_locks++;}
static void custom_unlock(void *p){CHECK(p==(void *)(uintptr_t)9);custom_unlocks++;}
int main(void){
 struct regmap_bus mmio={true},slow={false};struct regmap map;
 const struct regmap_config *saw_configs[]={&spm_8226_l2_regmap_config,&saw_regmap_config ,&spmi_regmap_config};
 for(unsigned int config_index=0;config_index<sizeof(saw_configs)/sizeof(saw_configs[0]);config_index++)for(rt=0;rt<2;rt++)for(in_ipi=0;in_ipi<2;in_ipi++){
  memset(&map,0,sizeof(map));clear_trace();
  CHECK(!select_lock(&map,saw_configs[config_index],config_index==2?&slow:&mmio));
  CHECK(!map.can_sleep&&map.lock_arg==&map);
  CHECK(map.lock==regmap_lock_raw_spinlock&&map.unlock==regmap_unlock_raw_spinlock);
  map.lock(map.lock_arg);map.unlock(map.lock_arg);
  CHECK(raw_locks==1&&raw_unlocks==1&&!spin_locks&&!mutex_locks);
  CHECK(!invalid_wait);cases++;
 }
 /* Independent controls exercise every generic decision route used above. */
 rt=1;in_ipi=0;struct regmap_config c={0};
 memset(&map,0,sizeof(map));clear_trace();CHECK(!select_lock(&map,&c,NULL));CHECK(map.can_sleep&&map.lock==regmap_lock_mutex);
 map.lock(map.lock_arg);map.unlock(map.lock_arg);CHECK(mutex_locks==1&&mutex_unlocks==1);cases++;
 c.fast_io=true;memset(&map,0,sizeof(map));clear_trace();CHECK(!select_lock(&map,&c,&slow));CHECK(!map.can_sleep&&map.lock==regmap_lock_spinlock);
 in_ipi=1;map.lock(map.lock_arg);map.unlock(map.lock_arg);CHECK(invalid_wait==1&&spin_locks==1&&spin_unlocks==1);cases++;
 c.disable_locking=true;memset(&map,0,sizeof(map));clear_trace();CHECK(!select_lock(&map,&c,&mmio));CHECK(map.lock==regmap_lock_unlock_none);map.lock(&map);map.unlock(&map);CHECK(!raw_locks&&!spin_locks&&!mutex_locks);cases++;
 c=(struct regmap_config){.lock=custom_lock,.unlock=custom_unlock,.lock_arg=(void *)(uintptr_t)9};
 memset(&map,0,sizeof(map));clear_trace();CHECK(!select_lock(&map,&c,&mmio));CHECK(map.lock==custom_lock&&map.lock_arg==c.lock_arg);map.lock(map.lock_arg);map.unlock(map.lock_arg);CHECK(custom_locks==1&&custom_unlocks==1);cases++;
 for(unsigned int mode=0;mode<3;mode++){
  c=(struct regmap_config){.use_hwlock=true,.hwlock_id=3,.hwlock_mode=mode};
  memset(&map,0,sizeof(map));clear_trace();CHECK(!select_lock(&map,&c,&mmio));map.lock(map.lock_arg);map.unlock(map.lock_arg);CHECK(hw_locks==1&&hw_unlocks==1);cases++;
 }
 memset(&map,0,sizeof(map));clear_trace();no_hw=1;CHECK(select_lock(&map,&c,&mmio)==-ENXIO);CHECK(!map.lock&&!map.unlock);cases++;
 printf("{\"cases\":%d,\"checks\":%d,\"failures\":%d}\n",cases,checks,failures);
 return failures?1:0;
}

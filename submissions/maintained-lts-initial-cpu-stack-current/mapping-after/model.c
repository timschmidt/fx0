
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define __iomem
#define UNUSED __attribute__((unused))
#define EINVAL 22
#define EIO 5
#define ENOMEM 12
#define EBUSY 16
#define ENOSYS 38
#define ENOENT 2
#define EPROBE_DEFER 517
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define PTR_ERR_OR_ZERO(p) (IS_ERR(p)?PTR_ERR(p):0)
#define ERR_CAST(p) ((void *)(p))
static int checks,failures,cases;
#define CHECK(x) do{checks++;if(!(x)){failures++;if(failures<9)fprintf(stderr,"line%d: %s\n",__LINE__,#x);}}while(0)
struct regmap_config {const char *name;unsigned int reg_bits,val_bits,reg_stride;bool use_raw_spinlock;};
struct device_node {int references;};
struct device {struct device_node *of_node;int id;};
struct regmap {int id;};
static struct device_node parents[2],saw;
static struct device devices[2]={{&parents[0],0},{&parents[1],1}};
static struct regmap private_maps[2]={{1},{2}},published_map={3};
static int registers[2],present,compatible,master,lookup_error,iomap_error,regmap_error;
static int parses,node_puts,lookups,iomaps,regmaps,property_calls,compatible_calls;
static struct device *current;
static const struct regmap_config saw_regmap_config = {
	.name = "saw",
	.reg_bits = 32,
	.val_bits = 32,
	.reg_stride = 4,
	.use_raw_spinlock = true,
};

static struct device_node *of_parse_phandle(struct device_node *parent,const char *name,int index){CHECK(parent==current->of_node&&!strcmp(name,"qcom,saw-reg")&&!index);parses++;if(!present)return NULL;saw.references++;return &saw;}
static bool UNUSED of_device_is_compatible(struct device_node *node,const char *name){CHECK(node==&saw&&saw.references==1&&!strcmp(name,"qcom,msm8226-saw2-v2.1-l2"));compatible_calls++;return compatible;}
static bool UNUSED of_property_read_bool(struct device_node *node,const char *name){CHECK(node==&saw&&saw.references==1&&!strcmp(name,"qcom,pmic-arbiter-master"));property_calls++;return master;}
static void of_node_put(struct device_node *node){CHECK(node==&saw&&saw.references==1);node_puts++;saw.references--;}
static struct regmap *syscon_node_to_regmap(struct device_node *node){CHECK(node==&saw&&saw.references==1);lookups++;return lookup_error?ERR_PTR(lookup_error):&published_map;}
static void *devm_of_iomap(struct device *dev,struct device_node *node,int index,void *size){CHECK(dev==current&&node==&saw&&saw.references==1&&!index&&!size);iomaps++;return iomap_error?ERR_PTR(iomap_error):&registers[dev->id];}
static struct regmap *devm_regmap_init_mmio(struct device *dev,void *base,const struct regmap_config *cfg){CHECK(dev==current&&base==&registers[dev->id]&&saw.references==0&&cfg==&saw_regmap_config);CHECK(cfg->reg_bits==32&&cfg->val_bits==32&&cfg->reg_stride==4);CHECK(cfg->use_raw_spinlock);regmaps++;return regmap_error?ERR_PTR(regmap_error):&private_maps[dev->id];}
static void reset(int id){present=1;compatible=master=lookup_error=iomap_error=regmap_error=0;parses=node_puts=lookups=iomaps=regmaps=property_calls=compatible_calls=0;saw.references=0;current=&devices[id];}
static void balanced(int expected_puts){CHECK(parses==1&&node_puts==expected_puts&&saw.references==0);}

static struct regmap *spmi_regulator_get_saw_regmap(struct device *dev)
{
	struct device_node *saw;
	struct regmap *map;
	void __iomem *base;

	saw = of_parse_phandle(dev->of_node, "qcom,saw-reg", 0);
	if (!saw)
		return NULL;

	if (of_device_is_compatible(saw, "qcom,msm8226-saw2-v2.1-l2") &&
	    of_property_read_bool(saw, "qcom,pmic-arbiter-master")) {
		/* The permanent SPM owner publishes this map after L2 setup. */
		map = syscon_node_to_regmap(saw);
		of_node_put(saw);
		return PTR_ERR_OR_ZERO(map) == -EINVAL ? ERR_PTR(-EPROBE_DEFER) : map;
	}

	/* Legacy SAWs retain the private raw-spinlock map required by the IPI. */
	base = devm_of_iomap(dev, saw, 0, NULL);
	of_node_put(saw);
	if (IS_ERR(base))
		return ERR_CAST(base);

	return devm_regmap_init_mmio(dev, base, &saw_regmap_config);
}

int main(void){
 struct regmap *map,*first;int errors[]={-EINVAL,-EIO,-ENOMEM,-ENOSYS,-EPROBE_DEFER,-ENOENT};
 for(int id=0;id<2;id++){
  reset(id);present=0;CHECK(!spmi_regulator_get_saw_regmap(current));balanced(0);CHECK(!lookups&&!iomaps&&!regmaps);cases++;
  for(int flags=0;flags<3;flags++){
   reset(id);compatible=flags&1;master=(flags>>1)&1;
   map=spmi_regulator_get_saw_regmap(current);CHECK(map==&private_maps[id]);balanced(1);
   CHECK(iomaps==1&&regmaps==1&&!lookups);CHECK(compatible_calls==1&&property_calls==compatible);cases++;
  }
  for(int error=-1;error<6;error++){
   reset(id);compatible=master=1;lookup_error=error<0?0:errors[error];
   map=spmi_regulator_get_saw_regmap(current);
   if(lookup_error)CHECK(IS_ERR(map)&&PTR_ERR(map)==(lookup_error==-EINVAL?-EPROBE_DEFER:lookup_error));else CHECK(map==&published_map);
   balanced(1);CHECK(lookups==1&&!iomaps&&!regmaps);cases++;
  }
  for(int stage=0;stage<2;stage++)for(int error=0;error<6;error++){
   reset(id);if(stage)regmap_error=errors[error];else iomap_error=errors[error];
   map=spmi_regulator_get_saw_regmap(current);CHECK(IS_ERR(map)&&PTR_ERR(map)==errors[error]);
   balanced(1);CHECK(!lookups&&iomaps==1&&regmaps==stage);cases++;
  }
 }
 /* A second device cannot replace the first device's private mapping. */
 reset(0);first=spmi_regulator_get_saw_regmap(current);reset(1);map=spmi_regulator_get_saw_regmap(current);
 CHECK(first==&private_maps[0]&&map==&private_maps[1]&&first!=map);cases++;
 printf("{\"cases\":%d,\"checks\":%d,\"failures\":%d}\n",cases,checks,failures);
 return failures?1:0;
}

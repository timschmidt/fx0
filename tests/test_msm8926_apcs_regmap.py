"""Exercise the CPR lookup of the APCS driver's register map."""

import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get("FX0_KERNEL_SOURCE", ROOT / "worktrees/linux-fx0-cpr"))
SOURCE = KERNEL / "drivers/pmdomain/qcom/cpr.c"

STUBS = r"""
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define __free(name)
#define EPROBE_DEFER 517
#define ERR_PTR(err) ((void *)(intptr_t)(err))
#define DL_FLAG_AUTOREMOVE_CONSUMER 1

struct device_node { bool compatible; };
struct device { struct device_node *of_node; };
struct platform_device { struct device dev; };
struct regmap { int marker; };
struct device_link { int marker; };

static struct device_node consumer_node, provider_node;
static struct platform_device provider;
static struct device consumer = { .of_node = &consumer_node };
static struct regmap existing;
static struct device_link link;
static bool phandle_present, device_present, bound, map_present, link_available;
static int refs, locks, maps_read, links_created;

static struct device_node *of_parse_phandle(struct device_node *node, const char *property,
                                            int index)
{
    assert(node == consumer.of_node && !strcmp(property, "qcom,apcs-syscon") && index == 0);
    return phandle_present ? &provider_node : NULL;
}

static bool of_device_is_compatible(struct device_node *node, const char *compatible)
{
    assert(node == &provider_node && !strcmp(compatible, "qcom,msm8226-apcs-kpss-global"));
    return node->compatible;
}

static struct platform_device *of_find_device_by_node(struct device_node *node)
{
    assert(node == &provider_node);
    if (!device_present)
        return NULL;
    refs++;
    return &provider;
}

static void device_lock(struct device *dev)
{
    assert(dev == &provider.dev && refs == 1 && locks == 0);
    locks++;
}

static bool device_is_bound(struct device *dev)
{
    assert(dev == &provider.dev && locks == 1);
    return bound;
}

static struct regmap *dev_get_regmap(struct device *dev, const char *name)
{
    assert(dev == &provider.dev && !name && locks == 1 && bound);
    maps_read++;
    return map_present ? &existing : NULL;
}

static struct device_link *device_link_add(struct device *client, struct device *supplier,
                                          int flags)
{
    assert(client == &consumer && supplier == &provider.dev);
    assert(flags == DL_FLAG_AUTOREMOVE_CONSUMER && locks == 1 && refs == 1);
    links_created++;
    return link_available ? &link : NULL;
}

static void device_unlock(struct device *dev)
{
    assert(dev == &provider.dev && locks == 1);
    locks--;
}

static void put_device(struct device *dev)
{
    assert(dev == &provider.dev && refs == 1 && locks == 0);
    refs--;
}
"""

CASES = r"""
int main(void)
{
    enum lookup_stage {
        NO_PHANDLE, WRONG_PROVIDER, NO_DEVICE, UNBOUND_DEVICE,
        NO_REGMAP, NO_LINK, READY,
    };
    struct regmap *expected[] = {
        [NO_PHANDLE] = ERR_PTR(-EINVAL),
        [WRONG_PROVIDER] = ERR_PTR(-EINVAL),
        [NO_DEVICE] = ERR_PTR(-EPROBE_DEFER),
        [UNBOUND_DEVICE] = ERR_PTR(-EPROBE_DEFER),
        [NO_REGMAP] = ERR_PTR(-ENODEV),
        [NO_LINK] = ERR_PTR(-EINVAL),
        [READY] = &existing,
    };

    for (enum lookup_stage stage = NO_PHANDLE; stage <= READY; stage++) {
        phandle_present = stage > NO_PHANDLE;
        provider_node.compatible = stage > WRONG_PROVIDER;
        device_present = stage > NO_DEVICE;
        bound = stage > UNBOUND_DEVICE;
        map_present = stage > NO_REGMAP;
        link_available = stage > NO_LINK;
        maps_read = links_created = 0;
        assert(cpr_msm8926_get_apcs(&consumer) == expected[stage]);
        assert(refs == 0 && locks == 0);
        assert(maps_read == (stage >= NO_REGMAP));
        assert(links_created == (stage >= NO_LINK));
    }
    return 0;
}
"""


class ApcsRegmapTests(unittest.TestCase):
    def test_lookup_reuses_the_bound_apcs_provider(self):
        if not SOURCE.is_file():
            self.skipTest("Candidate CPR source required")
        helper = re.search(r"static struct regmap \*cpr_msm8926_get_apcs\([^\n]+\)"
                           r"\n\{.*?\n\}", SOURCE.read_text(), flags=re.S)
        if not helper:
            self.skipTest("Candidate APCS lookup required")
        with tempfile.TemporaryDirectory() as work:
            path = Path(work)
            source = path / "apcs-regmap.c"
            source.write_text(STUBS + helper[0] + CASES)
            binary = path / "apcs-regmap"
            subprocess.run(["cc", "-Wall", "-Wextra", "-Werror",
                            str(source), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()

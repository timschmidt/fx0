// SPDX-License-Identifier: GPL-2.0-only
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int cases, checks, failures, allocations;
#define CHECK(x) do { checks++; if (!(x)) { fprintf(stderr, "CHECK %d: %s\n", __LINE__, #x); exit(1); } } while (0)
#define EXPECT(x) do { checks++; if (!(x)) { failures++; fprintf(stderr, "EXPECT %d: %s\n", __LINE__, #x); } } while (0)
struct device { int unused; };
struct device_node { int refs; };
struct qcom_smd_channel;
struct list_head { struct qcom_smd_channel *head, *owner; };
struct qcom_smd_channel { struct list_head list; struct qcom_smd_channel *next; char *name; };
struct qcom_smd_edge { struct device dev; struct list_head channels; struct device_node *of_node; };
static struct qcom_smd_edge *active;
#define to_smd_edge(p) ((struct qcom_smd_edge *)((char *)(p) - offsetof(struct qcom_smd_edge, dev)))
#define list_for_each_entry_safe(c,t,h,m) for ((c)=(h)->head; (c) && ((t)=(c)->next,1); (c)=(t))
static void list_del(struct list_head *node) { CHECK(active->channels.head == node->owner); active->channels.head = node->owner->next; }
static void of_node_put(struct device_node *node) { if (node) { CHECK(node->refs == 2); node->refs--; } }
static void *allocate(size_t n) { void *p = calloc(1,n); CHECK(p); allocations++; return p; }
static void kfree(void *p) { if (p) { CHECK(allocations > 0); allocations--; free(p); } }
/* ACTUAL_FUNCTION */
int main(void)
{
    for (int held = 0; held < 2; held++) for (int count = 0; count <= 16; count++) {
        struct device_node node = { .refs = held ? 2 : 1 };
        CHECK(!allocations); cases++;
        active = allocate(sizeof(*active));
        active->of_node = held ? &node : NULL;
        for (int n = 0; n < count; n++) {
            struct qcom_smd_channel *channel = allocate(sizeof(*channel));
            channel->name = allocate(8); memcpy(channel->name, "channel", 8);
            channel->list.owner = channel; channel->next = active->channels.head;
            active->channels.head = channel;
        }
        qcom_smd_edge_release(&active->dev); active = NULL;
        EXPECT(node.refs == 1); CHECK(!allocations);
    }
    printf("{\"cases\":%d,\"checks\":%d,\"failures\":%d}\n", cases, checks, failures);
    return failures ? 1 : 0;
}

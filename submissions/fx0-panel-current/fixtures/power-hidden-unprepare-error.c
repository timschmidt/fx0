/*
 * Extracted Linux panel/core fixture. GPL-2.0-only combined work.
 * See NOTICE and LICENSE.GPL-2.0 for original notices and licensing.
 */
// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * Copyright (C) 2013, NVIDIA Corporation.  All rights reserved.
 * Copyright (C) 2016 Laurent Pinchart <laurent.pinchart@ideasonboard.com>
 * Copyright (C) 2017 Broadcom
 */
// SPDX-License-Identifier: GPL-2.0-or-later
//
// core.c  --  Voltage/Current Regulator framework.
//
// Copyright 2007, 2008 Wolfson Microelectronics PLC.
// Copyright 2008 SlimLogic Ltd.
//
// Author: Liam Girdwood <lrg@slimlogic.co.uk>
/*
 * MIPI DSI Bus
 *
 * Copyright (C) 2012-2013, Samsung Electronics, Co., Ltd.
 * Andrzej Hajda <a.hajda@samsung.com>
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the
 * "Software"), to deal in the Software without restriction, including
 * without limitation the rights to use, copy, modify, merge, publish,
 * distribute, sub license, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to
 * the following conditions:
 *
 * The above copyright notice and this permission notice (including the
 * next paragraph) shall be included in all copies or substantial portions
 * of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL
 * THE COPYRIGHT HOLDERS, AUTHORS AND/OR ITS SUPPLIERS BE LIABLE FOR ANY CLAIM,
 * DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
 * OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
 * USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * MIPI DSI Bus
 *
 * Copyright (C) 2012-2013, Samsung Electronics, Co., Ltd.
 * Andrzej Hajda <a.hajda@samsung.com>
 */
/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Defines for Mobile Industry Processor Interface (MIPI(R))
 * Display Working Group standards: DSI, DCS, DBI, DPI
 *
 * Copyright (C) 2010 Guennadi Liakhovetski <g.liakhovetski@gmx.de>
 * Copyright (C) 2006 Nokia Corporation
 * Author: Imre Deak <imre.deak@nokia.com>
 */
// SPDX-License-Identifier: GPL-2.0-only
/*
 * LG Fx0 JDI in-cell panel, production board revisions.
 * Initialization data and power sequencing derived from the LG madai kernel.
 * Copyright (c) 2013, Code Aurora Forum. All rights reserved.
 * Copyright (c) 2012-2014, The Linux Foundation. All rights reserved.
 * Copyright (c) 2026 Timothy Schmidt
 */

// SPDX-License-Identifier: GPL-2.0-only
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define container_of(p,t,f) ((t *)((char *)(p)-offsetof(t,f)))
struct device {int unused;};
struct mutex {bool held;};
static void mutex_lock(struct mutex *m) {assert(!m->held);m->held=true;}
static void mutex_unlock(struct mutex *m) {assert(m->held);m->held=false;}
static unsigned logs;
#define dev_warn(...) ((void)logs++)
#define dev_info(...) ((void)logs++)
#define dev_err(...) ((void)logs++)
#define rdev_err(...) ((void)logs++)
#define WARN(condition,...) (condition)
#define lockdep_assert_held_once(...) ((void)0)
#define REGULATOR_CHANGE_STATUS 1
#define REGULATOR_EVENT_PRE_DISABLE 1
#define REGULATOR_EVENT_ABORT_DISABLE 2
#define REGULATOR_EVENT_DISABLE 3
#define NOTIFY_STOP_MASK 0x8000
#define PM_SUSPEND_ON 0
struct regulator;
struct regulation_constraints {bool always_on;};
struct regulator_dev {
 unsigned use_count;
 struct regulation_constraints *constraints;
 struct {unsigned n_coupled;} coupling_desc;
 struct regulator *supply;
};
struct regulator {struct regulator_dev *rdev;unsigned enable_count,uA_load;};
static int disable_error,enable_error,dsi_error;
static unsigned hardware_disables,gpio_calls,gpio_error_at;
static int _notifier_call_chain(struct regulator_dev *d,int event,void *arg)
{(void)d;(void)event;(void)arg;return 0;}
static bool regulator_ops_is_valid(struct regulator_dev *d,int op)
{(void)d;assert(op==REGULATOR_CHANGE_STATUS);return true;}
static int _regulator_do_disable(struct regulator_dev *d)
{assert(d->use_count==1);hardware_disables++;return disable_error;}
static int drms_uA_update(struct regulator_dev *d) {(void)d;return 0;}
static int regulator_balance_voltage(struct regulator_dev *d,int state)
{(void)d;(void)state;assert(false);return -EINVAL;}
struct drm_panel;
struct drm_panel_follower;
struct drm_panel_follower_funcs {
 int (*panel_prepared)(struct drm_panel_follower *);
 int (*panel_unpreparing)(struct drm_panel_follower *);
};
struct drm_panel_follower {const struct drm_panel_follower_funcs *funcs;};
struct drm_panel_funcs {int (*prepare)(struct drm_panel *);int (*unprepare)(struct drm_panel *);};
struct drm_panel {struct device *dev;const struct drm_panel_funcs *funcs;bool prepared;struct mutex follower_lock;int followers;};
#define list_for_each_entry(f,head,member) for((void)(head),(f)=NULL;(f);(f)=NULL)
struct mipi_dsi_device {struct device dev;unsigned long mode_flags;};
struct gpio_desc {int value;};
static int gpiod_direction_output(struct gpio_desc *g,int value)
{gpio_calls++;if(gpio_calls==gpio_error_at)return -EREMOTEIO;g->value=value;return 0;}
static void gpiod_set_value_cansleep(struct gpio_desc *g,int value) {g->value=value;}
static void usleep_range(unsigned low,unsigned high) {assert(low<=high);}
static void msleep(unsigned delay) {(void)delay;}

static int _regulator_handle_consumer_enable(struct regulator *regulator)
{
	int ret;
	struct regulator_dev *rdev = regulator->rdev;

	lockdep_assert_held_once(&rdev->mutex.base);

	regulator->enable_count++;
	if (regulator->uA_load && regulator->enable_count == 1) {
		ret = drms_uA_update(rdev);
		if (ret)
			regulator->enable_count--;
		return ret;
	}

	return 0;
}
static int _regulator_handle_consumer_disable(struct regulator *regulator)
{
	struct regulator_dev *rdev = regulator->rdev;

	lockdep_assert_held_once(&rdev->mutex.base);

	if (!regulator->enable_count) {
		rdev_err(rdev, "Underflow of regulator enable count\n");
		return -EINVAL;
	}

	regulator->enable_count--;
	if (regulator->uA_load && regulator->enable_count == 0)
		return drms_uA_update(rdev);

	return 0;
}
static int _regulator_disable(struct regulator *regulator)
{
	struct regulator_dev *rdev = regulator->rdev;
	int ret = 0;

	lockdep_assert_held_once(&rdev->mutex.base);

	if (WARN(regulator->enable_count == 0,
		 "unbalanced disables for %s\n", rdev_get_name(rdev)))
		return -EIO;

	if (regulator->enable_count == 1) {
	/* disabling last enable_count from this regulator */
		/* are we the last user and permitted to disable ? */
		if (rdev->use_count == 1 &&
		    (rdev->constraints && !rdev->constraints->always_on)) {

			/* we are last user */
			if (regulator_ops_is_valid(rdev, REGULATOR_CHANGE_STATUS)) {
				ret = _notifier_call_chain(rdev,
							   REGULATOR_EVENT_PRE_DISABLE,
							   NULL);
				if (ret & NOTIFY_STOP_MASK)
					return -EINVAL;

				ret = _regulator_do_disable(rdev);
				if (ret < 0) {
					rdev_err(rdev, "failed to disable: %pe\n", ERR_PTR(ret));
					_notifier_call_chain(rdev,
							REGULATOR_EVENT_ABORT_DISABLE,
							NULL);
					return ret;
				}
				_notifier_call_chain(rdev, REGULATOR_EVENT_DISABLE,
						NULL);
			}

			rdev->use_count = 0;
		} else if (rdev->use_count > 1) {
			rdev->use_count--;
		}
	}

	if (ret == 0)
		ret = _regulator_handle_consumer_disable(regulator);

	if (ret == 0 && rdev->coupling_desc.n_coupled > 1)
		ret = regulator_balance_voltage(rdev, PM_SUSPEND_ON);

	if (ret == 0 && rdev->use_count == 0 && rdev->supply)
		ret = _regulator_disable(rdev->supply);

	return ret;
}
/* Consumer-enable helper is real; rail enable itself is a contract stub. */
static int regulator_enable(struct regulator *r)
{
 if(enable_error)return enable_error;
 unsigned before=r->enable_count;int ret=_regulator_handle_consumer_enable(r);
 if(!ret && !before)r->rdev->use_count++;
 return ret;
}
static int regulator_disable(struct regulator *r) {return _regulator_disable(r);}
struct lg_fx0 {
	struct drm_panel panel;
	struct mipi_dsi_device *dsi;
	struct regulator *vdd;
	struct gpio_desc *reset;
	struct gpio_desc *io_enable;
	struct gpio_desc *positive_enable;
	struct gpio_desc *negative_enable;
	bool vdd_enabled;
	bool cleanup_pending;
};static inline struct lg_fx0 *to_lg_fx0(struct drm_panel *panel)
{
	return container_of(panel, struct lg_fx0, panel);
}
static int lg_fx0_on(struct lg_fx0 *p) {(void)p;return dsi_error;}

static int lg_fx0_power_off(struct lg_fx0 *priv)
{
	int ret, error;

	ret = gpiod_direction_output(priv->reset, 1);
	error = gpiod_direction_output(priv->negative_enable, 0);
	if (!ret)
		ret = error;
	usleep_range(10000, 11000);
	error = gpiod_direction_output(priv->positive_enable, 0);
	if (!ret)
		ret = error;
	usleep_range(10000, 11000);
	error = gpiod_direction_output(priv->io_enable, 0);
	if (!ret)
		ret = error;
	if (priv->vdd_enabled) {
		error = regulator_disable(priv->vdd);
		if (!error)
			priv->vdd_enabled = false;
		if (!ret)
			ret = error;
	}
	priv->cleanup_pending = ret != 0;
	if (ret)
		dev_err(&priv->dsi->dev, "Failed to power off panel: %d\n", ret);

	return ret;
}
static int lg_fx0_prepare(struct drm_panel *panel)
{
	struct lg_fx0 *priv = to_lg_fx0(panel);
	int ret;

	/* Finish a rejected cleanup before acquiring another supply reference. */
	if (priv->cleanup_pending) {
		ret = lg_fx0_power_off(priv);
		if (ret)
			return ret;
	}
	ret = regulator_enable(priv->vdd);
	if (ret)
		return ret;

	priv->vdd_enabled = true;
	ret = gpiod_direction_output(priv->reset, 1);
	if (ret)
		goto power_off;
	ret = gpiod_direction_output(priv->io_enable, 1);
	if (ret)
		goto power_off;
	usleep_range(10000, 11000);
	ret = gpiod_direction_output(priv->positive_enable, 1);
	if (ret)
		goto power_off;
	usleep_range(10000, 11000);
	ret = gpiod_direction_output(priv->negative_enable, 1);
	if (ret)
		goto power_off;
	usleep_range(10000, 11000);

	gpiod_set_value_cansleep(priv->reset, 1);
	usleep_range(10000, 11000);
	gpiod_set_value_cansleep(priv->reset, 0);
	msleep(20);
	gpiod_set_value_cansleep(priv->reset, 1);
	usleep_range(2000, 3000);
	gpiod_set_value_cansleep(priv->reset, 0);
	msleep(20);

	ret = lg_fx0_on(priv);
	if (!ret)
		return 0;

power_off:
	lg_fx0_power_off(priv);
	return ret;
}
static int lg_fx0_unprepare(struct drm_panel *panel)
{
	lg_fx0_power_off(to_lg_fx0(panel));
	return 0;
}
void drm_panel_prepare(struct drm_panel *panel)
{
	struct drm_panel_follower *follower;
	int ret;

	if (!panel)
		return;

	if (panel->prepared) {
		dev_warn(panel->dev, "Skipping prepare of already prepared panel\n");
		return;
	}

	mutex_lock(&panel->follower_lock);

	if (panel->funcs && panel->funcs->prepare) {
		ret = panel->funcs->prepare(panel);
		if (ret < 0)
			goto exit;
	}
	panel->prepared = true;

	list_for_each_entry(follower, &panel->followers, list) {
		if (!follower->funcs->panel_prepared)
			continue;

		ret = follower->funcs->panel_prepared(follower);
		if (ret < 0)
			dev_info(panel->dev, "%ps failed: %d\n",
				 follower->funcs->panel_prepared, ret);
	}

exit:
	mutex_unlock(&panel->follower_lock);
}
void drm_panel_unprepare(struct drm_panel *panel)
{
	struct drm_panel_follower *follower;
	int ret;

	if (!panel)
		return;

	/*
	 * If you are seeing the warning below it likely means one of two things:
	 * - Your panel driver incorrectly calls drm_panel_unprepare() in its
	 *   shutdown routine. You should delete this.
	 * - You are using panel-edp or panel-simple and your DRM modeset
	 *   driver's shutdown() callback happened after the panel's shutdown().
	 *   In this case the warning is harmless though ideally you should
	 *   figure out how to reverse the order of the shutdown() callbacks.
	 */
	if (!panel->prepared) {
		dev_warn(panel->dev, "Skipping unprepare of already unprepared panel\n");
		return;
	}

	mutex_lock(&panel->follower_lock);

	list_for_each_entry(follower, &panel->followers, list) {
		if (!follower->funcs->panel_unpreparing)
			continue;

		ret = follower->funcs->panel_unpreparing(follower);
		if (ret < 0)
			dev_info(panel->dev, "%ps failed: %d\n",
				 follower->funcs->panel_unpreparing, ret);
	}

	if (panel->funcs && panel->funcs->unprepare) {
		ret = panel->funcs->unprepare(panel);
		if (ret < 0)
			goto exit;
	}
	panel->prepared = false;

exit:
	mutex_unlock(&panel->follower_lock);
}
static void setup(struct lg_fx0 *p,struct regulator *reg,struct regulator_dev *rd,
                  struct regulation_constraints *constraints,struct gpio_desc *gp)
{
 memset(p,0,sizeof(*p));memset(reg,0,sizeof(*reg));memset(rd,0,sizeof(*rd));
 memset(gp,0,4*sizeof(*gp));*constraints=(struct regulation_constraints){0};
 rd->constraints=constraints;rd->coupling_desc.n_coupled=1;reg->rdev=rd;
 p->vdd=reg;p->reset=&gp[0];p->io_enable=&gp[1];p->positive_enable=&gp[2];p->negative_enable=&gp[3];
 static struct mipi_dsi_device dsi;static struct device dev;
 static const struct drm_panel_funcs funcs={.prepare=lg_fx0_prepare,.unprepare=lg_fx0_unprepare};
 p->dsi=&dsi;p->panel.dev=&dev;p->panel.funcs=&funcs;
 disable_error=enable_error=dsi_error=0;gpio_calls=gpio_error_at=hardware_disables=0;
}
int main(void)
{
 unsigned cases=0,broken=0;
 struct lg_fx0 p;struct regulator reg;struct regulator_dev rd;struct regulation_constraints constraints;struct gpio_desc gp[4];
 const unsigned cycles[]={1,2,5,10};
 for(unsigned c=0;c<4;c++) {
  setup(&p,&reg,&rd,&constraints,gp);
  for(unsigned i=0;i<cycles[c];i++) {
   drm_panel_prepare(&p.panel);assert(p.panel.prepared && reg.enable_count==1 && rd.use_count==1);
   drm_panel_unprepare(&p.panel);assert(!p.panel.prepared && !reg.enable_count && !rd.use_count);
  }
  cases++;
 }
 setup(&p,&reg,&rd,&constraints,gp);rd.use_count=1; /* One other consumer. */
 drm_panel_prepare(&p.panel);disable_error=-EIO;drm_panel_unprepare(&p.panel);
 assert(!p.panel.prepared && !reg.enable_count && rd.use_count==1 && !hardware_disables);cases++;

 setup(&p,&reg,&rd,&constraints,gp);drm_panel_prepare(&p.panel);disable_error=-EIO;
 drm_panel_unprepare(&p.panel);assert(reg.enable_count==1 && rd.use_count==1 && hardware_disables==1);
 bool lost=!p.panel.prepared;
 disable_error=0;drm_panel_unprepare(&p.panel); /* Retry a rejected unprepare. */
 drm_panel_prepare(&p.panel);drm_panel_unprepare(&p.panel);
 broken+=lost || reg.enable_count!=0 || rd.use_count!=0;cases++;

 for(unsigned kind=0;kind<2;kind++) {
  setup(&p,&reg,&rd,&constraints,gp);disable_error=-EIO;
  if(kind==0)dsi_error=-ETIMEDOUT;else gpio_error_at=2;
  drm_panel_prepare(&p.panel);
  assert(!p.panel.prepared && reg.enable_count==1 && rd.use_count==1 && hardware_disables==1);
  disable_error=dsi_error=0;gpio_error_at=0;
  drm_panel_prepare(&p.panel);assert(p.panel.prepared);
  drm_panel_unprepare(&p.panel);
  broken+=reg.enable_count!=0 || rd.use_count!=0;cases++;
 }

 for(unsigned offset=1;offset<=4;offset++) {
  setup(&p,&reg,&rd,&constraints,gp);drm_panel_prepare(&p.panel);
  gpio_error_at=gpio_calls+offset;drm_panel_unprepare(&p.panel);
  bool lost=!p.panel.prepared;
  gpio_error_at=0;drm_panel_unprepare(&p.panel);
  drm_panel_prepare(&p.panel);drm_panel_unprepare(&p.panel);
  broken+=lost || reg.enable_count!=0 || rd.use_count!=0;cases++;
 }
 setup(&p,&reg,&rd,&constraints,gp);dsi_error=-ETIMEDOUT;disable_error=-EIO;
 drm_panel_prepare(&p.panel);
 bool excess=reg.enable_count!=1;
 for(unsigned retry=0;retry<2;retry++) {
  drm_panel_prepare(&p.panel);excess|=reg.enable_count!=1;
 }
 dsi_error=disable_error=0;drm_panel_prepare(&p.panel);drm_panel_unprepare(&p.panel);
 broken+=excess || reg.enable_count!=0 || rd.use_count!=0;cases++;

 setup(&p,&reg,&rd,&constraints,gp);enable_error=-EIO;
 drm_panel_prepare(&p.panel);
 assert(!p.panel.prepared && !reg.enable_count && !rd.use_count && !gpio_calls);
 enable_error=0;drm_panel_prepare(&p.panel);drm_panel_unprepare(&p.panel);
 assert(!reg.enable_count && !rd.use_count);cases++;
 for(unsigned kind=0;kind<2;kind++) {
  setup(&p,&reg,&rd,&constraints,gp);
  if(kind==0)dsi_error=-ETIMEDOUT;else gpio_error_at=2;
  drm_panel_prepare(&p.panel);assert(!p.panel.prepared && !reg.enable_count && !rd.use_count);
  dsi_error=0;gpio_error_at=0;drm_panel_prepare(&p.panel);drm_panel_unprepare(&p.panel);
  assert(!reg.enable_count && !rd.use_count);cases++;
 }
 printf("cases=%u broken=%u\n",cases,broken);return broken?1:0;
}

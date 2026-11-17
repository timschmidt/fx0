/* SPDX-License-Identifier: GPL-2.0-or-later */
static struct inv_sensors_timestamp make_state(u32 clock, u32 mult)
{
	struct inv_sensors_timestamp ts;
	struct inv_sensors_timestamp_chip chip = {clock, 20, clock * mult};

	inv_sensors_timestamp_init(&ts, &chip);
	return ts;
}

static void initialized(struct inv_sensors_timestamp *ts)
{
#if MODEL_HAS_INIT
	ts->init = true;
#else
	(void)ts;
#endif
}

static void basic(void)
{
	static const u32 clocks[] = {125000, 1000000};
	static const u32 multipliers[] = {1, 2, 4, 8, 20, 32, 100, 1000};
	struct inv_sensors_timestamp ts, before;
	struct inv_sensors_timestamp_acc acc = {0};
	u64 sum;
	u32 i, j, n, step;

	group = 0;
	for (i = 0; i < ARRAY_SIZE(clocks); i++) {
		for (j = 0; j < ARRAY_SIZE(multipliers); j++) {
			cases++;
			ts = make_state(clocks[i], multipliers[j]);
			CHECK(ts.mult == multipliers[j]);
			CHECK(ts.period == clocks[i] * multipliers[j]);
			CHECK(ts.chip_period.val == clocks[i]);
			CHECK(ts.min_period == clocks[i] * 98 / 100);
			CHECK(ts.max_period == clocks[i] * 102 / 100);
			before = ts;
			inv_sensors_timestamp_interrupt(&ts, 0, 1000000000000LL);
			CHECK(memcmp(&ts, &before, sizeof(ts)) == 0);
			CHECK(!inv_validate_period(&ts, ts.min_period * ts.mult));
			CHECK(!inv_validate_period(&ts, ts.max_period * ts.mult));
			CHECK(inv_validate_period(&ts, ts.period));
			CHECK(inv_sensors_timestamp_update_odr(&ts, ts.period, true) == 0);
			CHECK(ts.new_mult == 0);
			CHECK(inv_sensors_timestamp_update_odr(&ts, ts.period * 2, true) == 0);
			CHECK(ts.new_mult == ts.mult * 2);
			CHECK(inv_sensors_timestamp_update_odr(&ts, ts.period, true) == -EAGAIN);
			inv_sensors_timestamp_apply_odr(&ts, 0, 0, 0);
			CHECK(ts.new_mult == 0);
			CHECK(ts.period == clocks[i] * multipliers[j] * 2);
			for (n = 0; n < 16; n++)
				CHECK(inv_sensors_timestamp_pop(&ts) == (s64)(n + 1) * ts.period);
		}
	}
	for (step = 0; step < 160; step++) {
		cases++;
		inv_update_acc(&acc, 125000 + step * 3);
		sum = 0;
		n = step + 1 < 32 ? step + 1 : 32;
		for (i = step + 1 - n; i <= step; i++)
			sum += 125000 + i * 3;
		CHECK(acc.val == sum / n);
		CHECK(acc.idx == (step + 1) % 32);
	}
}

static void watermark(void)
{
	static const u32 counts[] = {1, 2, 4, 16, 64};
	static const int drift[] = {-15, -5, 0, 5, 15};
	u32 i, j, n;
	s64 interrupt, last;
	struct inv_sensors_timestamp ts;

	group = 1;
	for (i = 0; i < ARRAY_SIZE(counts); i++) {
		for (j = 0; j < ARRAY_SIZE(drift); j++) {
			cases++;
			ts = make_state(1000000, 1);
			last = ts.timestamp = ts.it.up = 1000000000;
			initialized(&ts);
			interrupt = last + counts[i] * (1000000LL + drift[j] * 1000);
			inv_sensors_timestamp_interrupt(&ts, counts[i], interrupt);
			CHECK(ts.period == (u32)(1000000 + drift[j] * 1000));
			for (n = 0; n < counts[i]; n++) {
				s64 t = inv_sensors_timestamp_pop(&ts);
				CHECK(t > last);
				CHECK(t <= interrupt);
				last = t;
			}
			CHECK(last == interrupt);
		}
	}
}

static void long_measurement(void)
{
	static const int drift[] = {-1000, -500, 500, 1000};
	u32 i, n;
	s64 interrupt, last;
	struct inv_sensors_timestamp ts;

	group = 2;
	for (i = 0; i < ARRAY_SIZE(drift); i++) {
		cases++;
		ts = make_state(125000, 1);
		interrupt = 1000000000;
		inv_sensors_timestamp_interrupt(&ts, 1, interrupt);
		last = inv_sensors_timestamp_pop(&ts);
		for (n = 0; n < 10000; n++) {
			/* Individual intervals violate 2% jitter; pairs have a stable mean. */
			interrupt += 125000 + drift[i] + (n % 2 ? 25000 : -25000);
			inv_sensors_timestamp_interrupt(&ts, 1, interrupt);
			CHECK(ts.period >= ts.min_period && ts.period <= ts.max_period);
			s64 t = inv_sensors_timestamp_pop(&ts);
			CHECK(t > last);
			last = t;
		}
		CHECK(llabs((s64)ts.chip_period.val - (125000 + drift[i])) < 100);
	}
}

static void estimated_cap(void)
{
	static const u32 counts[] = {1, 2, 8, 32};
	static const u32 budgets[] = {980000, 990000, 1000000, 1010000};
	static const u32 estimates[] = {1000000, 1010000, 1019000};
	u32 i, j, k, n;
	s64 interrupt, last;
	struct inv_sensors_timestamp ts;

	group = 3;
	for (i = 0; i < ARRAY_SIZE(counts); i++) {
		for (j = 0; j < ARRAY_SIZE(budgets); j++) {
			for (k = 0; k < ARRAY_SIZE(estimates); k++) {
				cases++;
				ts = make_state(1000000, 1);
				last = ts.timestamp = 1000000000;
				initialized(&ts);
				ts.period = ts.chip_period.val = estimates[k];
				interrupt = last + (s64)counts[i] * budgets[j];
				ts.it.up = interrupt - (s64)counts[i] * 2000000;
				inv_sensors_timestamp_interrupt(&ts, counts[i], interrupt);
				for (n = 0; n < counts[i]; n++) {
					s64 t = inv_sensors_timestamp_pop(&ts);
					CHECK(t > last);
					CHECK(t <= interrupt);
					last = t;
				}
				CHECK(ts.period <= budgets[j]);
			}
		}
	}
}

static void reset_transition(void)
{
	static const u32 counts[] = {1, 2, 8, 32};
	static const u32 gaps[] = {1, 2, 8, 32, 64};
	u32 i, j, n;
	s64 last;
	struct inv_sensors_timestamp ts;

	group = 4;
	for (i = 0; i < ARRAY_SIZE(counts); i++) {
		for (j = 0; j < ARRAY_SIZE(gaps); j++) {
			cases++;
			ts = make_state(1000000, 1);
			last = ts.timestamp = 1000000000;
			ts.it.up = last;
			initialized(&ts);
			inv_sensors_timestamp_reset(&ts);
			CHECK(ts.it.lo == 0 && ts.it.up == 0);
			inv_sensors_timestamp_interrupt(&ts, counts[i], last + gaps[j] * 1000000LL);
			for (n = 0; n < counts[i]; n++) {
				s64 t = inv_sensors_timestamp_pop(&ts);
				CHECK(t > last);
				last = t;
			}
		}
	}
}

static void odr_transition(void)
{
	static const u32 counts[] = {1, 2, 8, 32};
	static const u32 multipliers[] = {1, 2, 4, 8, 20};
	u32 i, j, n;
	s64 last;
	struct inv_sensors_timestamp ts;

	group = 5;
	for (i = 0; i < ARRAY_SIZE(counts); i++) {
		for (j = 0; j < ARRAY_SIZE(multipliers); j++) {
			for (n = 0; n < counts[i]; n++) {
				cases++;
				ts = make_state(1000000, 32);
				last = ts.timestamp = 1000000000;
				ts.it.up = last + 1000000;
				initialized(&ts);
				CHECK(inv_sensors_timestamp_update_odr(&ts, multipliers[j] * 1000000, true) == 0);
				inv_sensors_timestamp_apply_odr(&ts, multipliers[j] * 1000000, counts[i], n);
				CHECK(ts.new_mult == 0 && ts.mult == multipliers[j]);
				CHECK(inv_sensors_timestamp_pop(&ts) > last);
			}
		}
	}
}

static void pending_odr(void)
{
	u32 i;
	struct inv_sensors_timestamp ts;
	struct inv_sensors_timestamp_acc acc;
	const s64 now = 2000000000;

	group = 6;
	for (i = 0; i < 16; i++) {
		cases++;
		ts = make_state(1000000, 1);
		initialized(&ts);
		ts.timestamp = now - 1000000;
		ts.it.up = now - (1001000 + i * 500);
#if MODEL_HAS_DELTA
		ts.delta.up = now - (1001000 + i * 500) * 20;
		ts.delta_counter = 19;
#endif
		acc = ts.chip_period;
		CHECK(inv_sensors_timestamp_update_odr(&ts, 2000000, true) == 0);
		inv_sensors_timestamp_interrupt(&ts, 1, now);
		CHECK(memcmp(&ts.chip_period, &acc, sizeof(acc)) == 0);
#if MODEL_HAS_DELTA
		CHECK(ts.delta_counter == 0 && ts.delta.up == now && ts.delta.lo == 0);
#endif
		CHECK(ts.it.up == now && ts.new_mult == 2);
	}
}

static s64 infeasible_budget_observation(void)
{
	struct inv_sensors_timestamp ts = make_state(1000000, 1);
	s64 now = 1000500000;

	/* A 0.5ms budget cannot fit a period constrained to at least 0.98ms. */
	ts.timestamp = 1000000000;
	ts.it.up = now - 2000000;
	initialized(&ts);
	inv_sensors_timestamp_interrupt(&ts, 1, now);
	return inv_sensors_timestamp_pop(&ts) - now;
}

int main(void)
{
	basic();
	watermark();
	long_measurement();
	estimated_cap();
	reset_transition();
	odr_transition();
	pending_odr();
	printf("{\"cases\":%lu,\"checks\":%lu,\"failures\":%lu,", cases, checks, failures);
	printf("\"group_failures\":[");
	for (u32 i = 0; i < 7; i++)
		printf("%s%lu", i ? "," : "", group_failures[i]);
	printf("],\"infeasible_budget_overshoot_ns\":%lld}\n", (long long)infeasible_budget_observation());
	return failures ? 1 : 0;
}

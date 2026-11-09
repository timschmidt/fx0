    def _validity_snapshot(self, label):
        snapshot = {
            "label": label,
            "devices": list(self.proxy.EnumerateDevices()),
            "present": self.get_dbus_display_property("IsPresent"),
            "percentage": self.get_dbus_display_property("Percentage"),
            "state": self.get_dbus_display_property("State"),
            "warning": self.get_dbus_display_property("WarningLevel"),
            "on_battery": self.get_dbus_property("OnBattery"),
        }
        print("FX0_VALIDITY_OBSERVATION " + json.dumps(snapshot), flush=True)
        return snapshot

    def _validity_add_battery(self, attributes):
        if "energy_full" not in attributes and "charge_full" not in attributes:
            attributes = ["energy_full", "10000000", "energy_full_design", "10000000"] + attributes
        return self.testbed.add_device(
            "power_supply", "validity-battery", None,
            ["type", "Battery", "present", "1", "status", "Discharging", "voltage_now", "3800000"] + attributes,
            [],
        )

    def _validity_assert_unusable(self, label, attributes):
        self._validity_add_battery(attributes)
        self.start_daemon()
        observed = self._validity_snapshot(label)
        self.assertEqual(observed["warning"], UP_DEVICE_LEVEL_NONE, observed)
        self.assertEqual(observed["devices"], [], observed)
        self.assertFalse(observed["present"], observed)

    def test_validity_empty_capacity(self):
        self._validity_assert_unusable("empty_capacity", ["capacity", ""])

    def test_validity_malformed_capacity(self):
        self._validity_assert_unusable("malformed_capacity", ["capacity", "invalid"])

    def test_validity_nan_capacity(self):
        self._validity_assert_unusable("nan_capacity", ["capacity", "nan"])

    def test_validity_infinite_capacity(self):
        self._validity_assert_unusable("infinite_capacity", ["capacity", "inf"])

    def test_validity_negative_capacity(self):
        self._validity_assert_unusable("negative_capacity", ["capacity", "-1"])

    def test_validity_malformed_energy(self):
        self._validity_assert_unusable(
            "malformed_energy", ["energy_full", "10000000", "energy_now", "invalid"]
        )

    def test_validity_malformed_average_energy(self):
        self._validity_assert_unusable(
            "malformed_average_energy", ["energy_full", "10000000", "energy_avg", "invalid"]
        )

    def test_validity_malformed_charge(self):
        self._validity_assert_unusable(
            "malformed_charge", ["charge_full", "2370000", "charge_now", "invalid"]
        )

    def _validity_read_error_environment(self, trigger=None):
        import unittest.mock
        library = os.environ["FX0_GUDEV_READ_ERROR_LIBRARY"]
        self.assertTrue(os.path.isfile(library), "Test shim not built")
        directory = tempfile.mkdtemp(prefix="upower-validity-")
        self.addCleanup(shutil.rmtree, directory)
        log = os.path.join(directory, "read-errors")
        environment = {
            "LD_PRELOAD": library + " " + os.environ.get("LD_PRELOAD", ""),
            "FX0_GUDEV_READ_ERROR_ATTRIBUTE": "capacity",
            "FX0_GUDEV_READ_ERROR_LOG": log,
        }
        if trigger:
            environment["FX0_GUDEV_READ_ERROR_TRIGGER"] = trigger
        return unittest.mock.patch.dict(os.environ, environment), log

    def test_validity_unavailable_coldplug_read(self):
        """GUdev NULL-read model, not an injected kernel sysfs errno."""
        self._validity_add_battery(["capacity", "50"])
        environment, log = self._validity_read_error_environment()
        with environment:
            self.start_daemon()
        self.assertTrue(os.path.getsize(log) > 0, "Read error not injected")
        observed = self._validity_snapshot("unavailable_coldplug_read")
        self.assertEqual(observed["devices"], [], observed)
        self.assertEqual(observed["warning"], UP_DEVICE_LEVEL_NONE, observed)

    def _validity_assert_refresh_not_empty(self, mode):
        bat = self._validity_add_battery(["capacity", "50"])
        if mode == "unavailable":
            directory = tempfile.mkdtemp(prefix="upower-validity-trigger-")
            self.addCleanup(shutil.rmtree, directory)
            trigger = os.path.join(directory, "enabled")
            environment, log = self._validity_read_error_environment(trigger)
            with environment:
                self.start_daemon()
        else:
            self.start_daemon()
        before = self._validity_snapshot(mode + "_before")
        self.assertEqual(before["percentage"], 50.0, before)
        self.assertEqual(before["warning"], UP_DEVICE_LEVEL_NONE, before)
        if mode == "unavailable":
            with open(trigger, "w"):
                pass
        else:
            self.testbed.set_attribute(bat, "capacity", "invalid")
        self.testbed.uevent(bat, "change")
        self.daemon_log.check_line("refreshing device for path " + bat, timeout=5)
        time.sleep(0.5)  # Allow the composite display-device idle update to run.
        after = self._validity_snapshot(mode + "_after")
        if mode == "unavailable":
            self.assertTrue(os.path.getsize(log) > 0, "Read error not injected")
        self.assertEqual(after["warning"], UP_DEVICE_LEVEL_NONE, after)
        self.assertEqual(after["percentage"], before["percentage"], after)

    def test_validity_malformed_refresh_not_empty(self):
        self._validity_assert_refresh_not_empty("malformed")

    def test_validity_unavailable_refresh_not_empty(self):
        self._validity_assert_refresh_not_empty("unavailable")

    def test_validity_ignored_supply_can_gain_telemetry(self):
        bat = self._validity_add_battery(["health", "Good"])
        self.start_daemon()
        before = self._validity_snapshot("ignored_before")
        self.assertEqual(before["devices"], [], before)
        self.testbed.set_attribute(bat, "capacity", "50")
        self.testbed.uevent(bat, "change")
        self.daemon_log.check_line("Received uevent change on device", timeout=5)
        time.sleep(0.5)
        after = self._validity_snapshot("ignored_after")
        self.assertEqual(len(after["devices"]), 1, after)
        self.assertTrue(after["present"], after)
        self.assertEqual(after["percentage"], 50.0, after)

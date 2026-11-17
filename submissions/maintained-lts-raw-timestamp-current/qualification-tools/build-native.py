# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib,json,os,signal,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';O=N/'native-01';O.mkdir();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();objects=['drivers/iio/adc/qcom-spmi-iadc.o','drivers/iio/industrialio-core.o','drivers/iio/industrialio-buffer.o','drivers/iio/industrialio-trigger.o','drivers/iio/buffer/industrialio-triggered-buffer.o','drivers/iio/industrialio-event.o','drivers/iio/buffer/kfifo_buf.o','drivers/iio/test/iio-test-format.o','drivers/iio/common/inv_sensors/inv_sensors_timestamp.o']+['drivers/iio/imu/inv_mpu6050/'+x+'.o' for x in ['inv_mpu_core','inv_mpu_ring','inv_mpu_trigger','inv_mpu_aux','inv_mpu_magn','inv_mpu_dmp','inv_mpu_i2c','inv_mpu_acpi','inv_mpu_spi']]+['drivers/phy/qualcomm/phy-qcom-usb-hs.o','drivers/phy/phy-core.o','drivers/usb/common/ulpi.o','drivers/usb/phy/phy-ulpi-viewport.o','drivers/iio/orientation/hid-sensor-rotation.o']+['drivers/iio/imu/inv_icm42600/'+x+'.o' for x in ['inv_icm42600_core','inv_icm42600_gyro','inv_icm42600_accel','inv_icm42600_temp','inv_icm42600_buffer','inv_icm42600_i2c','inv_icm42600_spi']];assert len(objects)==30;files=[f[:-2]+'.c' for f in objects];hashes={f:sha(C/f) for f in files};child=None;j=dict(passed=False,state='prepared',source_files=hashes,profiles=[],stages=[],ARM32_RT_unsupported_not_counted=True,phone_access=False,firmware_sensor_USB_execution=False);save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n')
try:
 for arch,rt,mode,acpi,seed in [('arm',False,'y',False,'native-01/arm-normal-CPU-enabled-system-on-out'),('arm64',False,'m',True,'native-01/arm64-normal-CPU-enabled-system-off-out'),('arm64',True,'m',True,'native-02/arm64-rt-CPU-enabled-system-off-out')]:
  label=arch+('-rt' if rt else '-normal')+'-IIO-PHY-'+mode;out=O/(label+'-out');out.mkdir();(out/'tmp').mkdir();(out/'.config').write_bytes((N.parent/'system-coordinator-01'/seed/'.config').read_bytes());env=os.environ|{'TMPDIR':str(out/'tmp'),'GIT_NO_LAZY_FETCH':'1'};args=['scripts/config','--file',str(out/'.config'),'--enable','EXPERT','--disable','COMPILE_TEST','--enable','MODULES']
  for sym in ['ARCH_QCOM','IIO','IIO_BUFFER','IIO_TRIGGER','IIO_TRIGGERED_BUFFER','IIO_KFIFO_BUF','I2C','SPI','SPI_MASTER','CRC32','FW_LOADER','KUNIT','EXTCON','HID','HID_SENSOR_HUB','USB_PHY','USB_ULPI']:
   args+=['--enable',sym]
  for sym in ['QCOM_SPMI_IADC','INV_MPU6050_I2C','INV_MPU6050_SPI','IIO_FORMAT_KUNIT_TEST','USB_ULPI_BUS','PHY_QCOM_USB_HS','HID_SENSOR_DEVICE_ROTATION','INV_ICM42600_I2C','INV_ICM42600_SPI']:args+=['--enable' if mode=='y' else '--module',sym]
  args+=['--enable' if acpi else '--disable','ACPI']
  if acpi:args+=['--enable','PCI','--enable','EFI']
  subprocess.run(args,cwd=C,check=True);make=['make','O='+str(out),'ARCH='+arch,'LLVM=-21','W=1','KCFLAGS=-Werror=incompatible-function-pointer-types','-j2']
  for phase,targets in [('config',['olddefconfig']),('objects',objects)]:
   log=O/(label+'-'+phase+'.log')
   with log.open('xb') as stream:
    child=subprocess.Popen(make+targets,cwd=C,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True);j.update(state='running '+label+' '+phase,active_PID=child.pid);save();code=child.wait(timeout=600)
   diagnostics=[l for l in log.read_text().splitlines() if 'warning:' in l.lower() or 'error:' in l.lower()];j['stages'].append(dict(profile=label,phase=phase,returncode=code,diagnostics=diagnostics,log_SHA256=sha(log)));save();assert code==0 and not diagnostics,diagnostics
  cfg=(out/'.config').read_text();assert ('CONFIG_PREEMPT_RT=y\n' in cfg)==rt and ('CONFIG_ACPI=y\n' in cfg)==acpi and 'CONFIG_CFI=y\n' in cfg and '# CONFIG_CFI_PERMISSIVE is not set\n' in cfg and '# CONFIG_COMPILE_TEST is not set\n' in cfg
  for sym in ['QCOM_SPMI_IADC','INV_MPU6050_IIO','INV_MPU6050_I2C','INV_MPU6050_SPI','IIO_FORMAT_KUNIT_TEST','USB_ULPI_BUS','PHY_QCOM_USB_HS','HID_SENSOR_DEVICE_ROTATION','INV_ICM42600_I2C','INV_ICM42600_SPI']:assert 'CONFIG_'+sym+'='+mode+'\n' in cfg,(sym,mode)
  assert 'CONFIG_USB_ULPI_VIEWPORT=y\n' in cfg
  assert all(sha(C/f)==h for f,h in hashes.items());j['profiles'].append(dict(profile=label,ARCH=arch,PREEMPT_RT=rt,ACPI=acpi,mode=mode,CFI=True,CFI_PERMISSIVE=False,config_SHA256=sha(out/'.config'),objects={f:sha(out/f) for f in objects}));save()
 j.update(passed=True,state='terminal success',native_objects=90)
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
print(json.dumps(dict(passed=True,native_objects=90)))

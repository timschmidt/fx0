"""Exercise the actual C NFC protocol/state machine without an NFC device."""
import errno
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
FLAGS=['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Wformat=2','-Wshadow','-fsanitize=address,undefined','-fno-sanitize-recover=all']
FAMILY_FAULTS=['wrong_sequence','wrong_header_pid','wrong_type','multipart','dump_interrupted','NOOP','DONE','OVERRUN','short_nlmsg','long_nlmsg','short_header','empty_datagram','trailing_byte','peer_pid','peer_groups','peer_family','peer_size','truncated','control_truncated','genl_command','genl_version','genl_reserved','short_attr','long_attr','nested_scalar','network_scalar','zero_attr','high_attr','string_not_terminated','duplicate_attr','family_version','family_name','reserved_id','positive_ack','INT_MIN_ack','wrong_echo','short_ack','duplicate_ack','duplicate_reply','ack_not_capped','ack_extack','ack_tail']
DEVICE_FAULTS=['device_index','device_name','protocols','powered_range','RF_active','powered_missing','duplicate_device']

class NFCStateTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.directory=tempfile.TemporaryDirectory();cls.base=Path(cls.directory.name)
  cls.harness=cls.base/'harness';cls.production=cls.base/'nfc-state'
  for source,out in [('tests/nfc_state_harness.c',cls.harness),('diagnostics/nfc-startup/nfc-state.c',cls.production)]:
   p=subprocess.run(['clang',*FLAGS,str(ROOT/source),'-o',str(out)],capture_output=True,text=True)
   if p.returncode:raise RuntimeError(p.stderr)
 @classmethod
 def tearDownClass(cls):cls.directory.cleanup()
 def case(self,mode,verb='up'):
  p=subprocess.run([str(self.harness),mode,verb],capture_output=True,text=True,timeout=5)
  self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stderr,'');return json.loads(p.stdout)
 def test_packet_length_and_byte_mutations_are_memory_safe(self):
  r=self.case('fuzz');self.assertEqual(r['iterations'],16384);self.assertEqual(r['mutation_sends'],0)
 def test_get_up_down_and_ack_ordering(self):
  for mode,verb,expected in [('normal','get',[3,1]),('normal','up',[3,1,2,1]),('normal','down',[3,1,3,1]),('ack_first','up',[3,1,2,1]),('coalesced','up',[3,1,2,1])]:
   with self.subTest(mode=mode,verb=verb):
    r=self.case(mode,verb);self.assertEqual(r['result'],0);self.assertEqual(r['commands'],expected);self.assertEqual(r['mutation_sends'],int(verb!='get'));self.assertEqual(r['powered_after'],int(verb=='up'))
 def test_malformed_family_datagrams_and_ack_rejected_before_mutation(self):
  for mode in FAMILY_FAULTS:
   with self.subTest(mode=mode):
    r=self.case(mode);self.assertEqual(r['result'],-1);self.assertEqual(r['error'],errno.EPROTO);self.assertFalse(r['mutation_attempted']);self.assertEqual(r['mutation_sends'],0);self.assertEqual(r['commands'],[3])
 def test_wrong_device_state_rejected_before_mutation(self):
  for mode in DEVICE_FAULTS:
   with self.subTest(mode=mode):
    r=self.case(mode);self.assertEqual(r['result'],-1);self.assertEqual(r['error'],errno.EPROTO);self.assertFalse(r['mutation_attempted']);self.assertEqual(r['commands'],[3,1])
 def test_ack_and_reply_are_both_required(self):
  for mode,error in [('missing_ack',errno.ETIMEDOUT),('missing_reply',errno.ETIMEDOUT),('negative_ack',errno.EPERM)]:
   with self.subTest(mode=mode):
    r=self.case(mode);self.assertEqual(r['result'],-1);self.assertEqual(r['error'],error);self.assertFalse(r['mutation_attempted']);self.assertEqual(r['commands'],[3])
 def test_uncertain_mutation_is_never_resent_or_cleaned_up(self):
  for mode,error in [('short_send',errno.EIO),('send_EINTR',errno.EINTR),('send_error',errno.EIO),('send_deadline',errno.ETIMEDOUT),('mutation_timeout',errno.ETIMEDOUT),('mutation_rejected',errno.ERFKILL)]:
   with self.subTest(mode=mode):
    r=self.case(mode);self.assertEqual(r['result'],-1);self.assertEqual(r['error'],error);self.assertTrue(r['mutation_attempted']);self.assertEqual(r['mutation_sends'],1);self.assertEqual(r['commands'],[3,1,2])
 def test_ack_success_still_requires_new_powered_state(self):
  r=self.case('not_applied');self.assertEqual(r['result'],-1);self.assertEqual(r['error'],errno.EPROTO);self.assertTrue(r['mutation_attempted']);self.assertEqual(r['commands'],[3,1,2,1])
 def test_repeated_up_or_down_is_not_sent(self):
  for mode,verb in [('already_up','up'),('already_down','down')]:
   with self.subTest(mode=mode):
    r=self.case(mode,verb);self.assertEqual(r['result'],-1);self.assertEqual(r['error'],errno.EALREADY);self.assertFalse(r['mutation_attempted']);self.assertEqual(r['commands'],[3,1])
 def test_unsupported_action_and_invalid_CLI_reach_no_netlink(self):
  r=self.case('normal','poll');self.assertEqual(r['result'],-1);self.assertEqual(r['error'],errno.EINVAL);self.assertEqual(r['commands'],[])
  for args in [[],['up'],['poll','0'],['fw','0'],['get','-1'],['get','+1'],['get','1x'],['get','4294967296'],['get','100000'],['get','0','extra'],['up','']]:
   with self.subTest(args=args):
    p=subprocess.run([str(self.production),*args],capture_output=True,text=True,timeout=5);self.assertEqual(p.returncode,2);self.assertEqual(p.stdout,'');self.assertIn('Usage:',p.stderr)

if __name__=='__main__':unittest.main()

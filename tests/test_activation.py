"""Verify activation gates without AWS, credentials or privileged commands."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class ActivationTests(unittest.TestCase):
    def run_fixture(self, existing_mode, warmup_exit):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);commands=root/'commands';commands.mkdir()
            (root/'.env').write_text('ROOSTOO_API_KEY=fixture\nROOSTOO_SECRET_KEY=fixture\n')
            log=root/'calls'
            fixtures={
                'id':'echo ssm-user',
                'stat':'echo 600',
                'systemctl':f'echo "--mode {existing_mode}"',
                'python3.11':f'echo "$*" >> "{log}"\ncase "$*" in *trading_bot.warmup*) exit {warmup_exit};; esac\nexit 0',
                'sudo':f'echo PRIVILEGED_MUTATION >> "{log}"\nexit 77',
            }
            for name,body in fixtures.items():
                p=commands/name;p.write_text('#!/bin/sh\n'+body+'\n');p.chmod(0o700)
            source=Path('deploy/activate_team116.sh').read_text().replace('project_root=/home/ssm-user/roostoo-hackathon-bot',f'project_root={root}')
            script=root/'activation.sh';script.write_text(source)
            result=subprocess.run(['bash',str(script)],env={**os.environ,'PATH':str(commands)+os.pathsep+os.environ['PATH']},capture_output=True,text=True)
            return result.returncode,log.read_text() if log.exists() else ''

    def test_failed_warmup_cannot_stop_or_install_service(self):
        code,calls=self.run_fixture('paper',1)
        self.assertEqual(code,1)
        self.assertIn('preflight',calls)
        self.assertIn('trading_bot.warmup',calls)
        self.assertNotIn('PRIVILEGED_MUTATION',calls)

    def test_existing_live_service_is_not_replaced(self):
        code,calls=self.run_fixture('live',0)
        self.assertEqual(code,1)
        self.assertEqual(calls,'')


if __name__=='__main__':unittest.main()

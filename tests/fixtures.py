# SPDX-License-Identifier: Apache-2.0
"""Explicit test-only resources, never production defaults."""
def configure_resources():
 import control,alerts
 control.RESOURCES.clear();control.RESOURCES.update({
  'proxy':('Test proxy','user','test-proxy.service','connection stops'),
  'codex':('Test worker','user','test-worker.service','jobs stop'),
  'photos':('Test photos','container','test-photos','uploads stop'),
  'ml':('Test ML','container','test-ml','jobs stop'),
  'display':('Test display','system','pi-console-display.service','display stops'),
  'printer':('Test printer','system','cups-browsed.service','discovery stops')})
 alerts.DEFAULT['watch']=['photos','ml','proxy','codex']

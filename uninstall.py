#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compatibility entry point; preview unless --apply is supplied."""
import sys
from manage import main
if __name__=='__main__':
 sys.argv.insert(1,'uninstall');main()

#!/usr/bin/env python3
"""Supported BFT65B release interface; legacy repair dispatcher intentionally retired."""
import sys
sys.dont_write_bytecode=True
from workflow.engine import main
if __name__=='__main__':
    raise SystemExit(main())

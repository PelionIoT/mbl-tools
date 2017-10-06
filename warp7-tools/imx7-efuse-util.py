#!/usr/bin/python

# Copyright (c) 2017 Linaro, Ltd.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
# contributors may be used to endorse or promote products derived from this
# software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import print_function

import argparse
import binascii
import errno
import os
import struct
import sys
import logging

# There are 128 bits per fuse bank aka 4 32 bit DWORDs
# See i.MX 7Solo Applications Processor Reference Manual, Rev. 0.1, 08/2016
IMX7S_FUSES_PER_BANK            = 0x04
IMX7S_BYTES_PER_FUSE            = 0x04
IMX7S_FUSE_BANK_COUNT           = 0x10
IMX7S_SRK_FUSE_COUNT            = 0x08
IMX7S_SECURE_FUSE_BANK_START    = 0x06  # Ref Manual section 6.4.5.41
IMX7S_BOOT_CFG_BANK             = 0x01  # Ref Manual Table 6-19
IMX7S_BOOT_CFG0_WORD            = 0x03

# OCOTP_BOOT_CFG0 definitions - Section 6-19 Fuse-Map
OCOTP_BOOT_CFG0_FORCE_COLD_BOOT = 0b00100000000000000000000000000000
OCOTP_BOOT_CFG0_BT_FUSE_SEL     = 0b00010000000000000000000000000000
OCOTP_BOOT_CFG0_DIR_BT_DIS      = 0b00001000000000000000000000000000
OCOTP_BOOT_CFG0_SEC_CONFIG      = 0b00000010000000000000000000000000
OCOTP_BOOT_MODE_MASK            = 0b00000000000000001111000000000000
OCOTP_BOOT_CFG0_SD              = 0b00000000000000000001000000000000
OCOTP_BOOT_CFG0_MMC             = 0b00000000000000000010000000000000
OCOTP_BOOT_CFG0_NAND            = 0b00000000000000000011000000000000
OCOTP_BOOT_CFG0_QSPI            = 0b00000000000000000101000000000000
OCOTP_BOOT_CFG0_NOR             = 0b00000000000000000110000000000000


def fatal(msg, errcode):
    """Print an error message and exit with a defined exit code"""
    logging.error("Fatal : " + msg)
    sys.exit(errcode)


def open_file(path, mode):
    """Open a file in the specified mode or bail out trapping the IOError"""

    try:
        handle = open(path, mode)
        return handle

    except IOError as e:
        raise ValueError("%s %s" % (path, str(e)))


def string2dword(chunk):
    """Convert little endian string to little endian dword"""
    chunk = bytearray(chunk)
    chunk.reverse()
    fuse = int(binascii.hexlify(chunk), 16)
    return fuse


def print_fuse(chunk):
    """Print string formatted little endian to little-endian dword"""
    fuse = string2dword(chunk)
    print("\t0x%08x" % (fuse))


def seek_to_bank(fuse_handle, start_bank):
    """Move to the offset of the indicated bank in the memory map provided"""
    # Calculate offset and seek to the location
    offset = start_bank * IMX7S_FUSES_PER_BANK * IMX7S_BYTES_PER_FUSE
    fuse_handle.seek(offset)


def seek_to_register(fuse_handle, start_bank, fuse):
    """Move to the offset of a given fuse"""
    # Validate range
    if fuse >= IMX7S_FUSES_PER_BANK:
        estr = "fuse index " + str(fuse) + " out of bounds"
        fatal(estr, errno.EINVAL)

    # Seek to the bank
    seek_to_bank(fuse_handle, start_bank)

    # Seek to fuse offset
    offset = fuse * IMX7S_BYTES_PER_FUSE
    fuse_handle.seek(offset, os.SEEK_CUR)


def dump_fuse(fuse_handle, start_bank, bank_count):
    """Dump the set of fuses starting at start_bank for bank_count banks"""
    # Seek to offset of start_bank
    seek_to_bank(fuse_handle, start_bank)

    # Calculate end bank
    i = 0
    bank = start_bank
    end_bank = start_bank + bank_count

    # Display loop of dword values
    while True:
        if i == 0:
            if bank == end_bank:
                break
            print("Bank %d" % (bank))
            bank = bank + 1
        i = i + 1
        if i == IMX7S_FUSES_PER_BANK:
            i = 0
        chunk = fuse_handle.read(IMX7S_BYTES_PER_FUSE)
        if chunk:
            print_fuse(chunk)
        else:
            break


def prompt(prompt_string, pass_val):
    val = raw_input(prompt_string)
    if val != pass_val:
        print("Aborting operation")
        return False
    return True


def read_fuse_int(fuse_handle):
    """Read fuse setting"""
    chunk = fuse_handle.read(IMX7S_BYTES_PER_FUSE)
    if chunk == 0:
        estr = "Unable to read fuse bank = " + str(IMX7S_BOOT_CFG_BANK) + \
               " word " + str(IMX7S_BOOT_CFG0_WORD)
        fatal(estr, errno.ENODEV)
    fuse = string2dword(chunk)
    return fuse


def dump_boot_fuse(fuse_handle):
    """Dump boot fuse status

    Section 6.4.5.24:
        Address: 3035_0000h base + 470h offset = 3035_0470h => OCOTP_BOOT_CFG0
        Fuse Bank 1 word 3

    6.3.3 Table 6-19
        Fuse offset + 470h
        OCOTP_BOOT_CFG0
            29   => FORCE_COLD_BOOT(SBMR)
            28   => BT_FUSE_SEL
            27   => DIR_BT_DIS
            25   => SEC_CONFIG
            19:0 => BOOT_CFG
    """

    print('Boot Fuse settings')

    # Seek to bank
    seek_to_register(fuse_handle, IMX7S_BOOT_CFG_BANK, IMX7S_BOOT_CFG0_WORD)

    # Read fuse contents as integer
    fuse = read_fuse_int(fuse_handle)

    # Display bit-contents
    print('OCOTP_BOOT_CFG0 = 0x%08x' % fuse)
    print('\tFORCE_COLD_BOOT = %u'
          % bool((fuse & OCOTP_BOOT_CFG0_FORCE_COLD_BOOT)))
    print('\tBT_FUSE_SEL     = %u'
          % bool((fuse & OCOTP_BOOT_CFG0_BT_FUSE_SEL)))
    print('\tDIR_BT_DIS      = %u'
          % bool((fuse & OCOTP_BOOT_CFG0_DIR_BT_DIS)))
    print('\tSEC_CONFIG      = %u'
          % bool((fuse & OCOTP_BOOT_CFG0_SEC_CONFIG)))

    # Print the boot mode (higher order bits) lower order 'speed' bits TBD
    boot_mode = fuse & OCOTP_BOOT_MODE_MASK

    mode_select = {
        OCOTP_BOOT_CFG0_SD: "SD",
        OCOTP_BOOT_CFG0_MMC: "MMC/eMMC",
        OCOTP_BOOT_CFG0_NAND: "NAND",
        OCOTP_BOOT_CFG0_QSPI: "QSPI",
        OCOTP_BOOT_CFG0_NOR: "NOR",
    }
    mode = mode_select.get(boot_mode, "Unknown")
    print('\tBoot Mode       = {}'.format(mode))


def dump_srk_fuse(fuse_handle):
    """Dump the SRK fuse map"""
    print('Secure fuse keys')

    # Print from the SRK bank for two fuse bank iterations
    dump_fuse(fuse_handle, IMX7S_SECURE_FUSE_BANK_START, 2)


def prompt_user_write_srk_fuse(srk_file, nvmem_path, yesall):
    """Give the user the chance to abort before we burn SRK fuses"""
    if yesall is False:
        pstring = "Write key values in " + srk_file + " to SRK fuses => " \
                  + nvmem_path + " y/n "
        if prompt(pstring, 'y') is False:
            return False
    return True


def write_srk_fuse(fuse_handle, fuse_map_handle):
    """Write the SRK fuse map"""
    # Seek to offset of SRK fuses
    seek_to_bank(fuse_handle, IMX7S_SECURE_FUSE_BANK_START)

    i = 0
    while True:
        # Read input key
        chunk = fuse_map_handle.read(4)
        if chunk == 0:
            break
        fuse = string2dword(chunk)

        print("Key %d 0x%08x" % (i, fuse))
        i = i + 1

        # Write key to Linux driver interface
        fuse_handle.write(chunk)
        fuse_handle.flush()


def prompt_user_write_sec_config_bit(fuse_handle, yesall):
    """Give the user the chance to abort before we pop the SEC_CONFIG fuse"""
    dump_srk_fuse(fuse_handle)
    if yesall is False:
        pstring = "Lock part into secure-boot mode with above keys? " + " y/n "
        if prompt(pstring, 'y') is False:
            return False

        pstring = "Are you REALLY sure ?" + " y/n "
        if prompt(pstring, 'y') is False:
            return False
    return True


def validate_fuses(fuse_handle, fuse_count):
    """Go to the starting fuse bank address"""
    seek_to_bank(fuse_handle, IMX7S_SECURE_FUSE_BANK_START)

    # Validate at least one fuse is non-zero
    i = 0
    found = False
    while i < fuse_count:
        # Read input key
        chunk = fuse_handle.read(4)
        if chunk == 0:
            break
        fuse = string2dword(chunk)

        # Is SRK fuse non-zero ?
        if (fuse != 0x00000000):
            found = True
            break
        i = i + 1

    return found


def write_sec_config_bit(rfuse_handle, wfuse_handle):
    """Write the SRK fuse map"""
    # Validate the basic sanity of the fuse setup
    if validate_fuses(rfuse_handle, IMX7S_SRK_FUSE_COUNT) is False:
        dump_boot_fuse(rfuse_handle)
        estr = "Fuse validation fail"
        fatal(estr, errno.ENODEV)

    # Seek to bank
    seek_to_register(rfuse_handle, IMX7S_BOOT_CFG_BANK, IMX7S_BOOT_CFG0_WORD)
    seek_to_register(wfuse_handle, IMX7S_BOOT_CFG_BANK, IMX7S_BOOT_CFG0_WORD)

    # Read fuse contents as integer
    fuse = read_fuse_int(rfuse_handle)

    # Flip the bit
    if (fuse & OCOTP_BOOT_CFG0_SEC_CONFIG) == 0:
        fuse = fuse | OCOTP_BOOT_CFG0_SEC_CONFIG

    # Write new word back
    data = struct.pack("<I", fuse)
    wfuse_handle.write(data)
    wfuse_handle.flush()

    # dump initial state
    dump_boot_fuse(rfuse_handle)


def dump_path(path):
    """Show the given path"""
    print('Path : %s' % (path))


def parse_args():
    """Extract command line arguments"""
    parser = argparse.ArgumentParser()

    parser.add_argument('-k',
                        help='keyfile containing data to write to fuses')

    parser.add_argument('-p',
                        default='/sys/bus/nvmem/devices/imx-ocotp0/nvmem',
                        help='path to write keyfile to')

    parser.add_argument('-l', action='store_true',
                        help='Lock part to secure mode - irrevocable')

    parser.add_argument('-y', action='store_true',
                        help='Yes to all prompts')

    parser.add_argument('-s', action='store_true',
                        help='Print fuse status')

    parser.add_argument('-d', action='store_true',
                        help='Dump entire fuse contents')

    return parser.parse_args()


def main():
    args = parse_args()

    rfuse_handle = open_file(args.p, 'rb')
    if args.d:
        dump_path(args.p)
        dump_fuse(rfuse_handle, 0, IMX7S_FUSE_BANK_COUNT)
    elif args.s:
        dump_path(args.p)
        dump_boot_fuse(rfuse_handle)
        dump_srk_fuse(rfuse_handle)
    else:
        # Open write fuse handle and input fuse keys if appropriate
        wfuse_handle = open_file(args.p, 'wb')
        if args.k:
            fuse_map_handle = open_file(args.k, 'a+b')

        # Burn fuses if promted by '-y' on the command line or 'y' at prompt
        if args.k and prompt_user_write_srk_fuse(args.k, args.p, args.y):
            write_srk_fuse(wfuse_handle, fuse_map_handle)

        # Burn the secure boot bit - CAUTION
        if args.l and prompt_user_write_sec_config_bit(rfuse_handle, args.y):
            write_sec_config_bit(rfuse_handle, wfuse_handle)

if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
# Copyright (c) 2019, Arm Limited and Contributors. All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Provides utilities for common operations on files."""

import contextlib
import datetime
import os
import pathlib
import shutil
import tempfile


class SectionMarkerError(Exception):
    """Base class for errors relating to section markers in files."""

    pass


class UnexpectedSectionMarkerError(SectionMarkerError):
    """Class for errors where an unexpected section marker is found."""

    def __init__(self, marker, line_no, path):
        """
        Initialize an object of this class.

        Args:
        * marker (str): the marker that was unexpected.
        * line (int): the line of the file at which the error occurred.
        * path (PathLike): file in which the error occurred.
        """
        super().__init__(
            'Unexpected marker "{}" found at line {} of file "{}"'.format(
                marker, str(line_no), path
            )
        )


class UnexpectedEofInSectionError(SectionMarkerError):
    """Class for errors where EOF is found inside a section."""

    def __init__(self, marker, path):
        """
        Initialize an object of this class.

        Args:
        * marker (str): the marker that was expected before EOF.
        * path (PathLike): file in which the error occurred.
        """
        super().__init__(
            'Unexpected EOF before marker "{}" in file "{}"'.format(
                marker, path
            )
        )


@contextlib.contextmanager
def atomic_read_modify_write_file(
    path, tmpdir=None, tmpdir_prefix="armw_", binary_mode=False
):
    """
    Provide support for doing atomic read-modify-write operations on files.

    This context manager:
    * Sets up a file-like object (call it "reader") reading from the specified
      file.
    * Sets up a file-like object (call it "writer") writing to a temporary
      file.
    * Yields the tuple (reader, writer) to the "with" block.
    * Atomically replaces the original file with the temporary file.

    Mandatory args:
    * path (PathLike): path to the file to modify.

    Optional args:
    * tmpdir (PathLike): path to a directory in which to create temporary
      files. Note that this directory must be on the same file system as the
      file being modified to ensure that replacing the original file with the
      temporary file is atomic. Default value is Path(path).parent.
    * tmpdir_prefix (str): string with which to prefix temporary file names.
    * binary_mode (bool): Open files in binary mode? Default: False.

    Example:
    to modify each line in a file using a modify_line function, you could
    write:
    ---------------------------------------------------------------------------
    with atomic_read_modify_write_file(path) as (reader, writer):
        for line in reader:
            writer.write(modify_line(line))
    ---------------------------------------------------------------------------
    """
    path = pathlib.Path(path)
    tmpdir = tmpdir or path.parent

    if binary_mode:
        read_mode = "rb"
        write_mode = "wb"
    else:
        read_mode = "rt"
        write_mode = "wt"

    # We only need to create a single temporary file, but if we were to just
    # use tempfile.TemporaryFile() we'd have to give up on it's automatic
    # cleanup because we need to replace the original file with the temporary
    # file after we've closed the files.
    #
    # To work around this, use tempfile.TemporaryDirectory() to create a
    # temporary directory containing the temporary file. The temporary
    # directory, including its contents, will be automatically cleaned up
    # _after_ we replace the original file with the temporary one (unless a
    # failure occurs and triggers early cleanup).
    with tempfile.TemporaryDirectory(
        dir=str(tmpdir), prefix=tmpdir_prefix
    ) as tmp_dir_path:
        tmp_dir_path = pathlib.Path(tmp_dir_path)
        tmp_file_name = "{}{}.tmp".format(tmpdir_prefix, path.name)
        tmp_file_path = tmp_dir_path / tmp_file_name

        with path.open(mode=read_mode) as orig_file:
            with tmp_file_path.open(mode=write_mode) as tmp_file:
                yield (orig_file, tmp_file)
        # Make sure the temporary file has the same owner, permissions, etc. as
        # the original before we do the replacement.
        shutil.copystat(str(path), str(tmp_file_path))
        os.replace(str(tmp_file_path), str(path))


@contextlib.contextmanager
def replace_section_in_file(
    path, section_name, tmpdir=None, comment_leader="#"
):
    r"""
    Create or replace a section bounded by marker comments in a file.

    This context manager is to make it easy to automatically add a section to a
    text file, bounded by marker comments, or replace a previously added
    section (bounded by marker comments) in a file.

    This context manager:
    * Sets up a temporary file.
    * Copies lines from the original file into the temporary file until it
      finds a BEGIN marker or the end of the file is reached. If it doesn't
      find a begin marker it adds one to the end of the file.
    * Writes a comment line to the temporary file stating the time that the
      file is being modified.
    * Yields a file-like object for writing to the temporary file to the "with"
      block.
    * Ignores any lines from the original file that appear before an END
      marker.
    * Writes an end marker to the end of the temporary file if the section
      didn't previously exist.
    * Atomically replaces the original file with the temporary file.

    Mandatory args:
    * path (PathLike): path to the file to modify.
    * section_name (str): a string added to marker comments to distinguish
      between different sections.

    Optional args:
    * tmpdir (PathLike): the path to a directory in which to create temporary
      files. This directory must be on the same file system as the file to
      modify. The default value, None, means "pathlib.Path(path).parent" in
      order to ensure that the directory is on the right file system.
    * comment_leader (str): A string that starts line comments in the file
      to modify. All lines automatically added by this context manager will
      start with comment_leader.

    Example:
    To create or replace a section with name "Foo config" in a file
    "/path/to/file.conf", (which uses ";" to begin line comments) you could
    write something like:

    ---------------------------------------------------------------------------
    with replace_section_in_file(
        "/path/to/file.conf",
        "Foo config",
        comment_leader=";"
    ) as foo_section:
        foo_section.write("enable foo\n")
        foo_section.write("foo_setting_x=bar\n")
    ---------------------------------------------------------------------------

    The file will end up with a section something like:

    ---------------------------------------------------------------------------
    ; BEGIN_AUTOGENERATED_SECTION: Foo config
    ; Last modified: 2019-04-18T11:06:54.177639
    enable foo
    foo_setting_x=bar
    ; END_AUTOGENERATED_SECTION: Foo config
    ---------------------------------------------------------------------------
    """
    begin_marker = _create_section_marker(
        comment_leader, "BEGIN", section_name
    )
    end_marker = _create_section_marker(comment_leader, "END", section_name)
    time_str = _create_last_modified_comment(comment_leader)

    with atomic_read_modify_write_file(
        path=path, tmpdir=tmpdir, tmpdir_prefix="rsif_"
    ) as (reader, writer):
        # Have we seen a BEGIN marker yet?
        found_section = False

        # Have we seen a BEGIN marker but not yet an END marker?
        in_section = False

        for line_no, line in enumerate(reader, 1):
            stripped_line = line.strip()
            if line == begin_marker:
                if found_section:
                    raise UnexpectedSectionMarkerError(
                        begin_marker.strip(), line_no, path
                    )
                found_section = True
                in_section = True
                writer.write(line)
                writer.write(time_str)
                yield writer
            elif line == end_marker:
                if not in_section:
                    raise UnexpectedSectionMarkerError(
                        end_marker.strip(), line_no, path
                    )
                writer.write(line)
                in_section = False
            elif not in_section:
                writer.write(line)

        if in_section:
            raise UnexpectedEofInSectionError(end_marker.strip(), path)

        if not found_section:
            writer.write(begin_marker)
            writer.write(time_str)
            yield writer
            writer.write(end_marker)


def ensure_is_regular_file(path):
    """
    Check that a file exists and is a regular file.

    Raises an exception on failure and does nothing on success

    Args:
    * path (PathLike): path to check.
    """
    path = pathlib.Path(path)
    if not path.exists():
        raise ValueError('"{}" does not exist'.format(path))
    if not path.is_file():
        raise ValueError('"{}" is not a regular file'.format(path))


def ensure_is_directory(path):
    """
    Check that a file exists and is a directory.

    Raises an exception on failure and does nothing on success

    Args:
    * path (PathLike): path to check.
    """
    path = pathlib.Path(path)
    if not path.exists():
        raise ValueError('"{}" does not exist'.format(path))
    if not path.is_dir():
        raise ValueError('"{}" is not a directory'.format(path))


def _create_section_marker(comment_leader, marker_type, section_name):
    return "{} {}_AUTOGENERATED_SECTION: {}\n".format(
        comment_leader, marker_type, section_name
    )


def _create_last_modified_comment(comment_leader):
    return "{} Last modified: {}\n".format(
        comment_leader, datetime.datetime.now().isoformat()
    )

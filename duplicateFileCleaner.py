#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
import hashlib
import json
import os

import sys

NORMAL = "\x1b[0m"
BOLD_RED = "\x1b[1;31;40m"
BOLD_GREEN = "\x1b[1;32;40m"
BOLD_YELLOW = "\x1b[1;33;40m"
BOLD_BLUE = "\x1b[1;34;40m"
BOLD_PURPLE = "\x1b[1;35;40m"
BOLD_CYAN = "\x1b[1;36;40m"
BOLD_WHITE = "\x1b[1;37;40m"

MD5_SUMS_FILE = 'files_and_md5_sums.json'

BASE_DIR = '/Users/rkitay/tmp/duplicate-file-cleaner'


class ArgsValidator(object):

    A_PATH_WITHIN_ROOT_DIR = '--cleanse-paths ({}) should point to a path within --root-dir ({})'
    POINT_TO_THE_SAME_PATH = '--root-dir ({}) and --cleanse-paths ({}) cannot point to the same path!'

    def __init__(self, args):
        self.cleanse_paths = args.cleanse_paths
        self.root_dir = args.root_dir
        self.action = args.action

    def validate(self):
        self.validate_root_dir_and_cleanse_paths()
        self.validate_cleanse_paths_and_action_match()
        self.validate_cleanse_with_previous_matches()

    def validate_root_dir_and_cleanse_paths(self):
        if self.cleanse_paths and len(self.cleanse_paths) > 0:
            root_dir = self.root_dir if not self.root_dir.endswith('/') else self.root_dir[:-1]
            for path_to_clean in self.cleanse_paths:
                path_to_clean = path_to_clean if not path_to_clean.endswith('/') else path_to_clean[:-1]
                if path_to_clean == root_dir:
                    parser.error(ArgsValidator.POINT_TO_THE_SAME_PATH.format(root_dir, path_to_clean))
                elif not path_to_clean.startswith(root_dir):
                    parser.error(ArgsValidator.A_PATH_WITHIN_ROOT_DIR.format(root_dir, path_to_clean))

    def validate_cleanse_paths_and_action_match(self):
        if self.cleanse_paths and len(self.cleanse_paths) > 0 and self.action == 'find':
            parser.error('--cleanse-paths cannot be passed with action "find"')
        if (not self.cleanse_paths or len(self.cleanse_paths) == 0) and self.action != 'find':
            parser.error('--cleanse-paths must be passed with action "{}"'.format(self.action))

    def validate_cleanse_with_previous_matches(self):
        if self.action == 'clean':
            if not os.path.exists('{}/{}'.format(self.root_dir, MD5_SUMS_FILE)):
                parser.error('Action "clean" must be run after "find"')


class DuplicateScanner(object):
    def __init__(self, root_dir, progress_indicator, ignored_dirs):
        self.root_dir = root_dir
        self.progress_indicator = progress_indicator
        self.ignored_dirs = ignored_dirs
        self.md5_sums = {}

    def scan(self):
        print (BOLD_GREEN + 'Starting scan for duplicates under <{}>'.format(self.root_dir) + NORMAL)
        print (BOLD_YELLOW + '')
        counter = 0
        for dir_path, dir_names, file_names in os.walk(self.root_dir, followlinks=True):

            if self.is_ignored_path(dir_path):
                continue

            for file_name in file_names:
                if file_name == '.DS_Store' or file_name.endswith('.BUP') or file_name.endswith('.IFO') or file_name.endswith('.VOB'):
                    continue
                md5 = self.md5_file(dir_path + '/' + file_name)
                files_with_current_md5 = []
                if self.md5_sums.has_key(md5):
                    files_with_current_md5 = self.md5_sums[md5]
                else:
                    self.md5_sums[md5] = files_with_current_md5

                files_with_current_md5.append((dir_path, file_name))

                counter += 1

                if counter % self.progress_indicator == 0:
                    print ('.'),
                    sys.stdout.flush()

        print ('\n' + BOLD_GREEN + 'Scan completed' + NORMAL)

    def md5_file(self, path_to_file):
        m = hashlib.md5()
        m.update(open(path_to_file, 'r').read())
        return m.hexdigest()

    def report(self):
        files_appearing_once = []
        files_appearing_more_than_once = []
        for md5, files in self.md5_sums.iteritems():
            if len(files) == 1:
                files_appearing_once.append('{}/{}'.format(files[0][0], (files[0][1])))
            else:
                for file in files:
                    files_appearing_more_than_once.append('{}/{}'.format(file[0], (file[1])))

        print (BOLD_GREEN + 'Files appearing once ({})'.format(len(files_appearing_once)))
        print ('-' * 50)
        for file in files_appearing_once:
            print (BOLD_GREEN + '{}'.format(file) + NORMAL)

        print (BOLD_YELLOW + 'Files appearing more than once ({})'.format(len(files_appearing_more_than_once)))
        print ('-' * 50)
        for file in files_appearing_more_than_once:
            print (BOLD_YELLOW + '{}'.format(file) + NORMAL)

    def save_results(self):
        json.dump(self.md5_sums, open('{}/{}'.format(self.root_dir, MD5_SUMS_FILE), 'w'), indent=2)

    def is_ignored_path(self, path):
        if self.ignored_dirs:
            for ignored_dir in self.ignored_dirs:
                if ignored_dir in path:
                    return True
        return False


class DuplicateCleaner(object):
    def __init__(self, cleanse_paths, demo, report):
        self.cleanse_paths = cleanse_paths
        self.demo = demo
        self.report = report
        self.files_to_delete = []
        self.total_files_counter = 0

    def clean(self, md5_sums):
        for md5, files in md5_sums.iteritems():
            self.total_files_counter += len(files)
            if len(files) > 1:
                self.mark_files_that_can_be_deleted(md5, files)

        for file_to_delete in self.files_to_delete:
            self.delete_file(file_to_delete[0], file_to_delete[1])

        print ('Total files: {}, total to delete: {}'.format(self.total_files_counter, len(self.files_to_delete)))

    def mark_files_that_can_be_deleted(self, md5, files):
        files_to_keep = filter(lambda path_and_file: not self.path_is_in_list(path_and_file[0]), files)
        files_to_cleanse = filter(lambda path_and_file: self.path_is_in_list(path_and_file[0]), files)
        if len(files_to_keep) > 0 and len(files_to_cleanse) > 0:
            self.files_to_delete.extend(files_to_cleanse)
            print ('-' * 100)
            print (u'{} => files to keep => {}'.format(md5, files_to_keep))
            print (u'{} => files to cleanse => {}'.format(md5, files_to_cleanse))
            # for dir, file in files_to_cleanse:
            #     move_to_temp(dir, file)

    def path_is_in_list(self, path):
        for path_to_cleanse in self.cleanse_paths:
            if path.startswith(path_to_cleanse):
                return True
        return False

    def delete_file(self, dir_path, file_name):
        new_dir = BASE_DIR + '/' + dir_path.replace('/', '_').replace(' ', '_')
        source = u'/'.join((dir_path, file_name))
        target = u'/'.join((new_dir, file_name))
        print (u'{} => {}'.format(source, target))
        if not self.demo:
            if not os.path.exists(new_dir):
                os.makedirs(new_dir)
            os.rename(source, target)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Finds and cleanse duplicate files')
    parser.add_argument('-a', '--action', choices=['find', 'clean', 'both'], help='Which action to perform')
    parser.add_argument('-r', '--root-dir', help='Root directory to scan')
    parser.add_argument('-c', '--cleanse-paths', nargs='+', required=False, help='The paths to "cleanse" if they contain duplicates from other paths')
    parser.add_argument('-i', '--ignored-dirs', nargs='+', required=False, help='The directories to ignore while finding duplicates')
    parser.add_argument('--progress-indicator', type=int, default=100, help='The number of files handled for which progress is displayed')
    parser.add_argument('--demo', dest='demo', action='store_true', help='For actions clean and both - does not delete files, only shows what would have been deleted')
    parser.add_argument('--no-report', dest='report', action='store_false', help='For actions find and both - prevents the report from being displayed')
    parser.set_defaults(demo=False)
    parser.set_defaults(report=True)

    argz = parser.parse_args()

    ArgsValidator(argz).validate()

    duplicateScanner = DuplicateScanner(argz.root_dir, argz.progress_indicator, argz.ignored_dirs)
    duplicateCleaner = DuplicateCleaner(argz.cleanse_paths, argz.demo, argz.report)

    if argz.action in ['find', 'both']:
        duplicateScanner.scan()
        if argz.report:
            duplicateScanner.report()
        duplicateScanner.save_results()
    if argz.action in ['clean', 'both']:
        md5_sums = json.load(open('{}/{}'.format(argz.root_dir, MD5_SUMS_FILE), 'r'))
        duplicateCleaner.clean(md5_sums)




    print argz
    # if args.action == 'find':
    #     print (args.action)

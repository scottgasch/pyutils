#!/usr/bin/env python3

# © Copyright 2021-2022, Scott Gasch

"""Global configuration driven by commandline arguments, environment variables,
saved configuration files, and zookeeper-based dynamic configurations.  This
works across several modules.

Example usage:

    In your file.py::

        from pyutils import config

        parser = config.add_commandline_args(
            "Module",
            "Args related to module doing the thing.",
        )
        parser.add_argument(
            "--module_do_the_thing",
            type=bool,
            default=True,
            help="Should the module do the thing?"
        )

    In your main.py::

        from pyutils import config

        parser = config.add_commandline_args(
            "Main",
            "A program that does the thing.",
        )
        parser.add_argument(
            "--dry_run",
            type=bool,
            default=False,
            help="Should we really do the thing?"
        )

        def main() -> None:
            config.parse()   # Very important, this must be invoked!

    If you set this up and remember to invoke config.parse(), all commandline
    arguments will play nicely together.  This is done automatically for you
    if you're using the :meth:`bootstrap.initialize` decorator on
    your program's entry point.  See :meth:`python_modules.bootstrap.initialize`
    for more details.::

        from pyutils import bootstrap

        @bootstrap.initialize
        def main():
            whatever

        if __name__ == '__main__':
            main()

    Either way, you'll get this behavior from the commandline::

        % main.py -h
        usage: main.py [-h]
                       [--module_do_the_thing MODULE_DO_THE_THING]
                       [--dry_run DRY_RUN]

        Module:
          Args related to module doing the thing.

          --module_do_the_thing MODULE_DO_THE_THING
                       Should the module do the thing?

        Main:
          A program that does the thing

          --dry_run
                       Should we really do the thing?

    Arguments themselves should be accessed via
    :code:`config.config['arg_name']`.  e.g.::

        if not config.config['dry_run']:
            module.do_the_thing()
"""

import argparse
import logging
import os
import pprint
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

# This module is commonly used by others in here and should avoid
# taking any unnecessary dependencies back on them.

# Make a copy of the original program arguments immediately upon module load.
PROGRAM_NAME: str = os.path.basename(sys.argv[0])
ORIG_ARGV: List[str] = sys.argv.copy()


class OptionalRawFormatter(argparse.HelpFormatter):
    """This formatter has the same bahavior as the normal argparse text
    formatter except when the help text of an argument begins with
    "RAW|".  In that case, the line breaks are preserved and the text
    is not wrapped.

    Use this, for example, when you need the helptext of an argument
    to have its spacing preserved exactly, e.g.::

        args.add_argument(
            '--mode',
            type=str,
            default='PLAY',
            choices=['CHEAT', 'AUTOPLAY', 'SELFTEST', 'PRECOMPUTE', 'PLAY'],
            metavar='MODE',
            help='''RAW|Our mode of operation.  One of:

                PLAY = play wordle with me!  Pick a random solution or
                       specify a solution with --template.

               CHEAT = given a --template and, optionally, --letters_in_word
                       and/or --letters_to_avoid, return the best guess word;

            AUTOPLAY = given a complete word in --template, guess it step
                       by step showing work;

            SELFTEST = autoplay every possible solution keeping track of
                       wins/losses and average number of guesses;

          PRECOMPUTE = populate hash table with optimal guesses.
            ''',
        )
    """

    def _split_lines(self, text, width):
        if text.startswith('RAW|'):
            return text[4:].splitlines()
        return argparse.HelpFormatter._split_lines(self, text, width)


# A global argparser that we will collect arguments in.  Each module (including
# us) will add arguments to a separate argument group.
ARGS = argparse.ArgumentParser(
    description=None,
    formatter_class=OptionalRawFormatter,
    fromfile_prefix_chars="@",
    epilog=f'{PROGRAM_NAME} uses config.py ({__file__}) for global, cross-module configuration setup and parsing.',
    # I don't fully understand why but when loaded by sphinx sometimes
    # the same module is loaded many times causing any arguments it
    # registers via module-level code to be redefined.  Work around
    # this iff the program is 'sphinx-build'
    conflict_handler='resolve' if PROGRAM_NAME == 'sphinx-build' else 'error',
)

# Arguments specific to config.py.  Other users should get their own group by
# invoking config.add_commandline_args.
GROUP = ARGS.add_argument_group(
    f'Global Config ({__file__})',
    'Args that control the global config itself; how meta!',
)
GROUP.add_argument(
    '--config_loadfile',
    metavar='FILENAME',
    default=None,
    help='Config file (populated via --config_savefile) from which to read args in lieu or in addition to those passed via the commandline.  Note that if the given path begins with "zk:" then it is interpreted as a zookeeper path instead of as a filesystem path.  When loading config from zookeeper, any argument with the string "dynamic" in the name (e.g. --module_dynamic_url) may be modified at runtime by changes made to zookeeper (using --config_savefile=zk:path).  You should therefore either write your code to handle dynamic argument changes or avoid naming arguments "dynamic" if you use zookeeper configuration paths.',
)
GROUP.add_argument(
    '--config_dump',
    default=False,
    action='store_true',
    help='Display the global configuration (possibly derived from multiple sources) on STDERR at program startup time.',
)
GROUP.add_argument(
    '--config_savefile',
    type=str,
    metavar='FILENAME',
    default=None,
    help='Populate a config file (compatible with --config_loadfile) with the given path for later use.  If the given path begins with "zk:" it is interpreted as a zookeeper path instead of a filesystem path.  When updating zookeeper-based configs, all running programs that read their configuration from zookeeper (via --config_loadfile=zk:path) at startup time will see their configuration dynamically updated; flags with "dynamic" in their names (e.g. --my_dynamic_flag) may have their values changed.  You should therefore either write your code to handle dynamic argument changes or avoid naming arguments "dynamic" if you use zookeeper configuration paths.',
)
GROUP.add_argument(
    '--config_rejects_unrecognized_arguments',
    default=False,
    action='store_true',
    help='If present, config will raise an exception if it doesn\'t recognize an argument.  The default behavior is to ignore unknown arguments so as to allow interoperability with programs that want to use their own argparse calls to parse their own, separate commandline args.',
)
GROUP.add_argument(
    '--config_exit_after_parse',
    default=False,
    action='store_true',
    help='If present, halt the program after parsing config.  Useful, for example, to write a --config_savefile and then terminate.',
)


class Config:
    """
    Everything in the config module used to be module-level functions and
    variables but it made the code ugly and harder to maintain.  Now, this
    class does the heavy lifting.  We still rely on some globals, though:

        ARGS and GROUP to interface with argparse
        PROGRAM_NAME stores argv[0] close to program invocation
        ORIG_ARGV stores the original argv list close to program invocation
        CONFIG and config: hold the (singleton) instance of this class.

    """

    def __init__(self):
        # Has our parse() method been invoked yet?
        self.config_parse_called = False

        # A configuration dictionary that will contain parsed
        # arguments.  This is the data that is most interesting to our
        # callers as it will hold the configuration result.
        self.config: Dict[str, Any] = {}

        # Defer logging messages until later when logging has been
        # initialized.
        self.saved_messages: List[str] = []

        # A zookeeper client that is lazily created so as to not incur
        # the latency of connecting to zookeeper for programs that are
        # not reading or writing their config data into zookeeper.
        self.zk: Optional[Any] = None

        # Per known zk file, what is the max version we have seen?
        self.max_version: Dict[str, int] = {}

    def __getitem__(self, key: str) -> Optional[Any]:
        """If someone uses []'s on us, pass it onto self.config."""
        return self.config.get(key, None)

    def __setitem__(self, key: str, value: Any) -> None:
        self.config[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self.config

    def get(self, key: str, default: Any = None) -> Optional[Any]:
        return self.config.get(key, default)

    @staticmethod
    def add_commandline_args(
        title: str, description: str = ""
    ) -> argparse._ArgumentGroup:
        """Create a new context for arguments and return a handle.

        Args:
            title: A title for your module's commandline arguments group.
            description: A helpful description of your module.

        Returns:
            An argparse._ArgumentGroup to be populated by the caller.
        """
        return ARGS.add_argument_group(title, description)

    @staticmethod
    def overwrite_argparse_epilog(msg: str) -> None:
        """Allows your code to override the default epilog created by
        argparse.

        Args:
            msg: The epilog message to substitute for the default.
        """
        ARGS.epilog = msg

    @staticmethod
    def is_flag_already_in_argv(var: str) -> bool:
        """Returns true if a particular flag is passed on the commandline
        and false otherwise.

        Args:
            var: The flag to search for.
        """
        for _ in sys.argv:
            if var in _:
                return True
        return False

    @staticmethod
    def print_usage() -> None:
        """Prints the normal help usage message out."""
        ARGS.print_help()

    @staticmethod
    def usage() -> str:
        """
        Returns:
            program usage help text as a string.
        """
        return ARGS.format_usage()

    @staticmethod
    def _reorder_arg_action_groups_before_help(entry_module: Optional[str]):
        """Internal.  Used to reorder the arguments before dumping out a
        generated help string such that the main program's arguments come
        last.

        """
        reordered_action_groups = []
        for grp in ARGS._action_groups:
            if entry_module is not None and entry_module in grp.title:  # type: ignore
                reordered_action_groups.append(grp)
            elif PROGRAM_NAME in GROUP.title:  # type: ignore
                reordered_action_groups.append(grp)
            else:
                reordered_action_groups.insert(0, grp)
        return reordered_action_groups

    @staticmethod
    def _parse_arg_into_env(arg: str) -> Optional[Tuple[str, str, List[str]]]:
        """Internal helper to parse commandling args into environment vars."""
        arg = arg.strip()
        if not arg.startswith('['):
            return None
        arg = arg.strip('[')
        if not arg.endswith(']'):
            return None
        arg = arg.strip(']')

        chunks = arg.split()
        if len(chunks) > 1:
            var = chunks[0]
        else:
            var = arg

        # Environment vars the same as flag names without
        # the initial -'s and in UPPERCASE.
        env = var.upper()
        while env[0] == '-':
            env = env[1:]
        return var, env, chunks

    @staticmethod
    def _to_bool(in_str: str) -> bool:
        """
        Args:
            in_str: the string to convert to boolean

        Returns:
            A boolean equivalent of the original string based on its contents.
            All conversion is case insensitive.  A positive boolean (True) is
            returned if the string value is any of the following:

            * "true"
            * "t"
            * "1"
            * "yes"
            * "y"
            * "on"

            Otherwise False is returned.

        >>> to_bool('True')
        True

        >>> to_bool('1')
        True

        >>> to_bool('yes')
        True

        >>> to_bool('no')
        False

        >>> to_bool('huh?')
        False

        >>> to_bool('on')
        True
        """
        return in_str.lower() in ("true", "1", "yes", "y", "t", "on")

    def _augment_sys_argv_from_environment_variables(self):
        """Internal.  Look at the system environment for variables that match
        commandline arg names.  This is done via some munging such that:

        :code:`--argument_to_match`

        ...is matched by:

        :code:`ARGUMENT_TO_MATCH`

        This allows users to set args via shell environment variables
        in lieu of passing them on the cmdline.

        """
        usage_message = Config.usage()
        optional = False
        arg = ''

        # Foreach valid optional commandline option (chunk) generate
        # its analogous environment variable.
        for chunk in usage_message.split():
            if chunk[0] == '[':
                optional = True
            if optional:
                arg += f'{chunk} '
                if chunk[-1] == ']':
                    optional = False
                    _ = Config._parse_arg_into_env(arg)
                    if _:
                        var, env, chunks = _
                        if env in os.environ:
                            if not Config.is_flag_already_in_argv(var):
                                value = os.environ[env]
                                self.saved_messages.append(
                                    f'Initialized from environment: {var} = {value}'
                                )
                                if len(chunks) == 1 and Config._to_bool(value):
                                    sys.argv.append(var)
                                elif len(chunks) > 1:
                                    sys.argv.append(var)
                                    sys.argv.append(value)
                    arg = ''

    def _process_dynamic_args(self, event):
        """Invoked as a callback when a zk-based config changed."""

        if not self.zk:
            return
        logger = logging.getLogger(__name__)
        try:
            contents, meta = self.zk.get(event.path, watch=self._process_dynamic_args)
            logger.debug('Update for %s at version=%d.', event.path, meta.version)
            logger.debug(
                'Max known version for %s is %d.',
                event.path,
                self.max_version.get(event.path, 0),
            )
        except Exception as e:
            raise Exception('Error reading data from zookeeper') from e

        # Make sure we process changes in order.
        if meta.version > self.max_version.get(event.path, 0):
            self.max_version[event.path] = meta.version
            contents = contents.decode()
            temp_argv = []
            for arg in contents.split():

                # Our rule is that arguments must contain the word
                # 'dynamic' if we are going to allow them to change at
                # runtime as a signal that the programmer is expecting
                # this.
                if 'dynamic' in arg:
                    temp_argv.append(arg)
                    logger.info("Updating %s from zookeeper async config change.", arg)

            if len(temp_argv) > 0:
                old_argv = sys.argv
                sys.argv = temp_argv
                known, _ = ARGS.parse_known_args()
                sys.argv = old_argv
                self.config.update(vars(known))

    def _read_config_from_zookeeper(self, zkpath: str) -> Optional[str]:
        from pyutils import zookeeper

        if not zkpath.startswith('/config/'):
            zkpath = '/config/' + zkpath
            zkpath = re.sub(r'//+', '/', zkpath)

        try:
            if self.zk is None:
                self.zk = zookeeper.get_started_zk_client()
            if not self.zk.exists(zkpath):
                return None

            # Note: we're putting a watch on this config file.  Our
            # _process_dynamic_args routine will be called to reparse
            # args when/if they change.
            contents, meta = self.zk.get(zkpath, watch=self._process_dynamic_args)
            contents = contents.decode()
            self.saved_messages.append(
                f'Setting {zkpath}\'s max_version to {meta.version}'
            )
            self.max_version[zkpath] = meta.version
            self.saved_messages.append(f'Read config from zookeeper {zkpath}.')
            return contents
        except Exception as e:
            self.saved_messages.append(
                f'Failed to read {zkpath} from zookeeper: exception {e}'
            )
            return None

    def _read_config_from_disk(self, filepath: str) -> Optional[str]:
        if not os.path.exists(filepath):
            return None
        with open(filepath, 'r') as rf:
            self.saved_messages.append(f'Read config from disk file {filepath}')
            return rf.read()

    def _augment_sys_argv_from_loadfile(self):
        """Internal.  Augment with arguments persisted in a saved file."""

        # Check for --config_loadfile in the args manually; argparse isn't
        # invoked yet and can't be yet.
        loadfile = None
        saw_other_args = False
        grab_next_arg = False
        for arg in sys.argv[1:]:
            if 'config_loadfile' in arg:
                pieces = arg.split('=')
                if len(pieces) > 1:
                    loadfile = pieces[1]
                else:
                    grab_next_arg = True
            elif grab_next_arg:
                loadfile = arg
            else:
                saw_other_args = True

        if not loadfile or len(loadfile) == 0:
            return

        # Get contents from wherever.
        contents = None
        if loadfile[:3] == 'zk:':
            contents = self._read_config_from_zookeeper(loadfile[3:])
        else:
            contents = self._read_config_from_disk(loadfile)

        if contents:
            if saw_other_args:
                msg = f'Augmenting commandline arguments with those from {loadfile}.'
            else:
                msg = f'Reading commandline arguments from {loadfile}.'
            print(msg, file=sys.stderr)
            self.saved_messages.append(msg)
        else:
            msg = f'Failed to read/parse contents from {loadfile}'
            print(msg, file=sys.stderr)
            self.saved_messages.append(msg)
            return

        # Augment args with new ones.
        newargs = [
            arg.strip('\n')
            for arg in contents.split('\n')
            if 'config_savefile' not in arg
        ]
        sys.argv += newargs

    def dump_config(self):
        """Print the current config to stdout."""
        print("Global Configuration:", file=sys.stderr)
        pprint.pprint(self.config, stream=sys.stderr)
        print()

    def _write_config_to_disk(self, data: str, filepath: str) -> None:
        with open(filepath, 'w') as wf:
            wf.write(data)

    def _write_config_to_zookeeper(self, data: str, zkpath: str) -> None:
        if not zkpath.startswith('/config/'):
            zkpath = '/config/' + zkpath
            zkpath = re.sub(r'//+', '/', zkpath)
        try:
            if not self.zk:
                from pyutils import zookeeper

                self.zk = zookeeper.get_started_zk_client()
            encoded_data = data.encode()
            if len(encoded_data) > 1024 * 1024:
                raise Exception(
                    f'Saved args are too large ({len(encoded_data)} bytes exceeds zk limit)'
                )
            if not self.zk.exists(zkpath):
                self.zk.create(zkpath, encoded_data)
                self.saved_messages.append(
                    f'Just created {zkpath}; setting its max_version to 0'
                )
                self.max_version[zkpath] = 0
            else:
                meta = self.zk.set(zkpath, encoded_data)
                self.saved_messages.append(
                    f'Setting {zkpath}\'s max_version to {meta.version}'
                )
                self.max_version[zkpath] = meta.version
        except Exception as e:
            raise Exception(f'Failed to create zookeeper path {zkpath}') from e
        self.saved_messages.append(f'Saved config to zookeeper in {zkpath}')

    def parse(self, entry_module: Optional[str]) -> Dict[str, Any]:
        """Main program should call this early in main().  Note that the
        :code:`bootstrap.initialize` wrapper takes care of this automatically.
        This should only be called once per program invocation.

        """
        if self.config_parse_called:
            return self.config

        # If we're about to do the usage message dump, put the main
        # module's argument group last in the list (if possible) so that
        # when the user passes -h or --help, it will be visible on the
        # screen w/o scrolling.
        for arg in sys.argv:
            if arg in ('--help', '-h'):
                if entry_module is not None:
                    entry_module = os.path.basename(entry_module)
                ARGS._action_groups = Config._reorder_arg_action_groups_before_help(
                    entry_module
                )

        # Examine the environment for variables that match known flags.
        # For a flag called --example_flag the corresponding environment
        # variable would be called EXAMPLE_FLAG.  If found, hackily add
        # these into sys.argv to be parsed.
        self._augment_sys_argv_from_environment_variables()

        # Look for loadfile and read/parse it if present.  This also
        # works by jamming these values onto sys.argv.
        self._augment_sys_argv_from_loadfile()

        # Parse (possibly augmented, possibly completely overwritten)
        # commandline args with argparse normally and populate config.
        known, unknown = ARGS.parse_known_args()
        self.config.update(vars(known))

        # Reconstruct the argv with unrecognized flags for the benefit of
        # future argument parsers.  For example, unittest_main in python
        # has some of its own flags.  If we didn't recognize it, maybe
        # someone else will.
        if len(unknown) > 0:
            if config['config_rejects_unrecognized_arguments']:
                raise Exception(
                    f'Encountered unrecognized config argument(s) {unknown} with --config_rejects_unrecognized_arguments enabled; halting.'
                )
            self.saved_messages.append(
                f'Config encountered unrecognized commandline arguments: {unknown}'
            )
        sys.argv = sys.argv[:1] + unknown

        # Check for savefile and populate it if requested.
        savefile = config['config_savefile']
        if savefile and len(savefile) > 0:
            data = '\n'.join(ORIG_ARGV[1:])
            if savefile[:3] == 'zk:':
                self._write_config_to_zookeeper(savefile[3:], data)
            else:
                self._write_config_to_disk(savefile, data)

        # Also dump the config on stderr if requested.
        if config['config_dump']:
            self.dump_config()

        self.config_parse_called = True
        if config['config_exit_after_parse']:
            print("Exiting because of --config_exit_after_parse.")
            if self.zk:
                self.zk.stop()
            sys.exit(0)
        return self.config

    def has_been_parsed(self) -> bool:
        """Returns True iff the global config has already been parsed"""
        return self.config_parse_called

    def late_logging(self):
        """Log messages saved earlier now that logging has been initialized."""
        logger = logging.getLogger(__name__)
        logger.debug('Original commandline was: %s', ORIG_ARGV)
        for _ in self.saved_messages:
            logger.debug(_)


# A global singleton instance of the Config class.
CONFIG = Config()

# A lot of client code uses config.config['whatever'] to lookup
# configuration so to preserve this we make this, config.config, with
# a __getitem__ method on it.
config = CONFIG

# Config didn't use to be a class; it was a mess of module-level
# functions and data.  The functions below preserve the old interface
# so that existing clients do not need to be changed.  As you can see,
# they mostly just thunk into the config class.


def add_commandline_args(title: str, description: str = "") -> argparse._ArgumentGroup:
    """Create a new context for arguments and return a handle.  An alias
    for config.config.add_commandline_args.

    Args:
        title: A title for your module's commandline arguments group.
        description: A helpful description of your module.

    Returns:
        An argparse._ArgumentGroup to be populated by the caller.
    """
    return CONFIG.add_commandline_args(title, description)


def parse(entry_module: Optional[str]) -> Dict[str, Any]:
    """Main program should call this early in main().  Note that the
    :code:`bootstrap.initialize` wrapper takes care of this automatically.
    This should only be called once per program invocation.  Subsequent
    calls do not reparse the configuration settings but rather just
    return the current state.
    """
    return CONFIG.parse(entry_module)


def has_been_parsed() -> bool:
    """Returns True iff the global config has already been parsed"""
    return CONFIG.has_been_parsed()


def late_logging() -> None:
    """Log messages saved earlier now that logging has been initialized."""
    CONFIG.late_logging()


def dump_config() -> None:
    """Print the current config to stdout."""
    CONFIG.dump_config()


def overwrite_argparse_epilog(msg: str) -> None:
    """Allows your code to override the default epilog created by
    argparse.

    Args:
        msg: The epilog message to substitute for the default.
    """
    Config.overwrite_argparse_epilog(msg)


def is_flag_already_in_argv(var: str) -> bool:
    """Returns true if a particular flag is passed on the commandline
    and false otherwise.

    Args:
        var: The flag to search for.
    """
    return Config.is_flag_already_in_argv(var)


def print_usage() -> None:
    """Prints the normal help usage message out."""
    Config.print_usage()


def usage() -> str:
    """
    Returns:
        program usage help text as a string.
    """
    return Config.usage()

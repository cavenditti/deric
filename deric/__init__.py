"""Improved cli definition experience.

Allows defining CLI commands in Pydantic-way, with automatic argparse and toml config
file definitions and parsing.

It was at first somewhat similar to https://github.com/SupImDos/pydantic-argparse,
I'm not using it because I didn't like some of that code and doesn't cover
all of our requirements.
"""
from __future__ import annotations
import abc
import argparse
from collections.abc import Iterable
import logging
from types import SimpleNamespace
from typing import Any, Tuple, Type
from copy import deepcopy
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from tomlkit import parse
from pydantic import Field, create_model

from deric.logs import setup_logging


class RuntimeConfig(SimpleNamespace):
    """Runtime configuration."""

    def to_dict(self):
        """Recursively convert to dict."""
        d = {}
        for k, v in vars(self).items():
            if isinstance(v, RuntimeConfig):
                d[k] = v.to_dict()
            else:
                d[k] = v
        return d


def make_namespace(d: Any):
    """Recursively convert dict to namespace."""
    if isinstance(d, dict):
        return RuntimeConfig(**{k: make_namespace(v) for k, v in d.items()})
    return d


def add_missing_fields(
    model_def: dict,
    field: str,
    field_type: Type,
    default: Any,
    description,
) -> dict:
    """Add missing attributes to dataclass."""
    if field not in model_def:
        model_def[field] = arg(field_type, default, description)
    return model_def


class _CommandMeta(abc.ABCMeta):
    """Metaclass for Command classes.

    Used to automatically set parents of a subcommand
    """

    def __new__(cls, name, bases, dct):
        x = super().__new__(cls, name, bases, dct)
        x.set_parent(None)
        return x


class Command(metaclass=_CommandMeta):
    """Generic CLI command."""

    name: str
    description: str

    Config: dict[str, tuple[type, Any]]

    subcommands: Iterable[Type[Command]] = set()

    parent: Type[Command] | None = None

    @classmethod
    def set_parent(cls, parent):
        """Recursively set parent commands."""
        cls.parent = parent
        for subcmd in cls.subcommands:
            subcmd.set_parent(cls)

    @classmethod
    def _with_log_file(cls, default="run.log") -> Type[Command]:
        # Add config, log, etc if it's the main command
        kls = deepcopy(cls)

        # allow with no explicit Config
        config = cls.Config if hasattr(cls, "Config") else {}

        kls.Config = add_missing_fields(
            deepcopy(config), "log_file", str, default, "Path of run log",
        )
        return kls

    # "config_file", str, "config.toml", "Config file to use"

    def __init__(self) -> None:
        """Parse and validate settings on object instantiation.

        `Command` configs are validated using Pydantic and `config` attribute is set
        with a `RuntimeConfig` generated from it.
        """
        # add missing fields if not specified by user. Methods using these are
        # classmethods so this must be done on the class and not the instance.
        if not hasattr(self.__class__, "Config"):
            self.__class__.Config = {}

        super().__init__()
        if self.parent:
            return

        parser = self._populate_subcommands()

        args = parser.parse_args()
        config = vars(args)

        # Good-looking logging to console and file
        # TODO how to handle config_file and log_file if not specified in the Command subclass config?
        if "log_file" in config:
            setup_logging(config["log_file"])

        if "config_file" in config:
            path = config["config_file"]
            with open(path, "r") as file:
                tomlconfig = parse(file.read())
                file_config = dict(tomlconfig)

            # Update config with values from cli (they should take precedence over config files).
            defaults = self.default_config().to_dict()
            args_config = {
                k: v
                for k, v in vars(args).items()
                if v is not None
                and k != "config_file"
                and (k not in defaults or v != defaults[k])
                and v != PydanticUndefined
                # FIXME the special handling of "config_file" is really ugly
            }
            defaults.update(file_config)
            defaults.update(args_config)
            config = defaults
            config["config_file"] = path

        self._subcmd_to_run: list[Command] = [self]
        validated_config = self.validate_config(config, self._subcmd_to_run)
        self.config: RuntimeConfig = make_namespace(validated_config)

        try:
            # update logging configuration after having read the config file
            logging.getLogger().setLevel(self.config.logging.loglevel)
        except AttributeError:
            pass

    @classmethod
    def is_subcommand(cls):
        """Check if cls.parent is not None."""
        return cls.parent is not None

    @abc.abstractmethod
    def run(self, config: RuntimeConfig):
        """Run for the command."""

    @classmethod
    def default_config(
        cls, _subcommand: Tuple[str, RuntimeConfig] | None = None, *, validate=False, **kwargs,
    ):
        """Get default config for command (and parents)."""
        # get prefix from all parents names
        kls = cls
        parents = [kls]
        while kls.parent is not None:
            parents.append(kls.parent)
            kls = kls.parent
        parents.reverse()
        prefix = "_".join((x.name for x in parents))
        if prefix:
            prefix = prefix + "_"

        relevant = {
            k.removeprefix(prefix): v for k, v in kwargs.items() if k.startswith(prefix)
        }

        config_model = create_model("config", **cls.Config)
        if validate:
            config_model_instance = config_model(**relevant)
        else:
            config_model_instance = config_model.model_construct(**relevant)
        config_dict = config_model_instance.model_dump()

        if _subcommand:
            config_dict[_subcommand[0]] = _subcommand[1]

        own_config = make_namespace(config_dict)

        if cls.parent:
            return cls.parent.default_config(
                _subcommand=(cls.name, own_config),
                **{k: v for k, v in kwargs.items() if not k.startswith(prefix)},
            )
        return own_config

    @classmethod
    def _populate_arguments(
        cls,
        *,
        parser: argparse.ArgumentParser,
        prefix="",
    ) -> argparse.ArgumentParser:
        """Create argparse ArgumentParser from model fields.

        Args:
        ----
            parser: parser to use (means we're in a subparser)
        """
        # Add Pydantic model to an ArgumentParser
        if not hasattr(cls, "Config"):
            cls.Config = {}

        def parser_args(name: str, ftype: type, field: FieldInfo) -> tuple[list, dict]:
            return (
                [
                    # "-" + name[0],  # short form
                    "--"
                    + name.replace("_", "-"),  # long form
                ],
                {
                    "dest": name
                    if cls.name == parser.prog
                    else f"{prefix}{cls.name}_{name}",
                    "type": ftype if ftype in (int, float, str) else str,
                    "action": "append"
                    if ftype in (set[str], list[str])
                    else "store",
                    "default": field.default,
                    "help": field.description,
                },
            )

        # Turn the fields of the model as arguments of the parser
        for name, (ftype, field) in cls.Config.items():
            # ignore fields not marked to be ignored in cli
            if (
                field.json_schema_extra
                and "cli" in field.json_schema_extra
                and not field.json_schema_extra["cli"]
            ):
                continue

            args, kwargs = parser_args(name, ftype, field)

            # booleans are special
            if ftype == bool:
                kwargs.pop("type")  # no type when using `store_true`
                kwargs["action"] = "store_true"

            parser.add_argument(
                *args,
                **kwargs,
            )
        return parser

    @classmethod
    def _populate_subcommands(cls, parser: argparse.ArgumentParser | None = None):
        """Add subcommands and relative arguments to argparse parser."""
        parser = (
            argparse.ArgumentParser(
                prog=cls.name,
                description=cls.description,
                # epilog=cls.epilog,
            )
            if not parser
            else parser
        )

        cls._populate_arguments(parser=parser)

        if not cls.subcommands:
            return parser

        subparsers = parser.add_subparsers(
            dest=cls.name + "_subcommand",
            title=cls.name + "_subcommand",
            required=True,
            description="valid subcommands",
            help="addtional help",
        )

        # if main_cmd and isinstance(field.type, ModelMetaclass):
        for cmd in cls.subcommands:
            # create new subparsers
            new_subcommand = subparsers.add_parser(cmd.name, help=cmd.description)
            # set function to run for new subcommand
            # new_subcommand.set_defaults(func=cmd.run)

            # also populate arguments
            cmd._populate_arguments(parser=new_subcommand, prefix=cls.name + "_")

            if cmd.subcommands:
                cmd._populate_subcommands(parser=new_subcommand)
        return parser

    @classmethod
    def validate_config(cls, relevant: dict, cmds: list[Command]) -> dict:
        """Parse and validate config.

        Command configs are validated using Pydantic and a dict is returned.
        """
        config_model = create_model("config", **cls.Config)
        config_model_instance = config_model(**relevant)
        config = config_model_instance.model_dump()

        # FIXME this is needed because of the way we handle relevant configs
        # below (when we recursively call validate_config).
        if "subcommand" in relevant:
            relevant[cls.name + "_subcommand"] = relevant.pop("subcommand")

        if cls.name + "_subcommand" in relevant:
            subcommand = relevant[cls.name + "_subcommand"]
            config["subcommand"] = subcommand
            for cmd in cls.subcommands:
                if cmd.name == subcommand:
                    # instantiate subcommand and put run method in the queue
                    cmds.append(cmd())

                    # FIXME this needs a complete reworking
                    command_dict = relevant[cmd.name] if cmd.name in relevant else {}
                    command_dict.update(
                        {
                            k.removeprefix(cls.name + "_").removeprefix(
                                cmd.name + "_",
                            ): v
                            for k, v in relevant.items()
                            if k.startswith(cmd.name + "_")
                            or k.startswith(f"{cls.name}_{cmd.name}_")
                        },
                    )

                    # validate subcommand config
                    cmd_config = cmd.validate_config(
                        command_dict,
                        cmds,
                    )
                    # remove subcommand keys from main config
                    relevant = {
                        k: v
                        for k, v in relevant.items()
                        if not k.startswith(cmd.name + "_")
                    }
                    config[cmd.name] = cmd_config
        return config

    def start(self):
        """Call `cmd.run()` for each subcommand.

        Should always be called on main command
        """
        if self.parent:
            raise RuntimeError("Run main command instead")

        for command in self._subcmd_to_run:
            logging.info("Running %s", command.name)
            command.run(self.config)


def arg(argtype, default, description, **kwargs):
    """Shortcut for pydantic.Field, returning a tuple to pass to create_model."""
    return (argtype, Field(default=default, description=description, json_schema_extra=kwargs))

def config(**kwargs):
    """Alternative to writing arg each time, doesn't support extra keyword arguments."""
    return {k:arg(*v) for k,v in kwargs.items()}

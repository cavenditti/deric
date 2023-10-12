"""
Improved cli definition experience.

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
from pydantic.dataclasses import dataclass
from copy import deepcopy
from pydantic.fields import FieldInfo

from tomlkit import parse
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from deric.utils.logging import setup_logging


class RuntimeConfig(SimpleNamespace):
    def to_dict(self):
        """
        Recursively convert to dict
        """
        d = {}
        for k, v in vars(self).items():
            if isinstance(v, RuntimeConfig):
                d[k] = v.to_dict()
            else:
                d[k] = v
        return d

    def __str__(self) -> str:
        """
        Pretty printing
        """
        return self.to_dict().__str__()


def make_namespace(d: Any):
    """
    Recursively convert dict to namespace
    """
    if isinstance(d, dict):
        return RuntimeConfig(**{k: make_namespace(v) for k, v in d.items()})
    else:
        return d


def add_missing_fields(
    model: Type,
    field: str,
    field_type: Type,
    default: Any,
    description,
) -> Type:
    """
    Adds missing attributes to dataclass.
    """
    if not hasattr(model, field):
        setattr(
            model,
            field,
            Field(
                default,
                description=description,
            ),
        )
        model.__annotations__[field] = field_type
    return model


class _empty:
    pass


class CommandMeta(abc.ABCMeta):
    def __new__(cls, name, bases, dct):
        x = super().__new__(cls, name, bases, dct)
        x.set_parent(None)
        return x


class Command(metaclass=CommandMeta):
    """
    Generic CLI command.
    """

    name: str
    description: str

    Config: Type
    subcommands: Iterable[Type[Command]] = set()

    parent: Type[Command] | None = None

    @classmethod
    def set_parent(cls, parent):
        """
        Recursively set parent commands
        """
        cls.parent = parent
        for subcmd in cls.subcommands:
            subcmd.set_parent(cls)

    @classmethod
    def with_logfile(cls, default="run.log") -> Type[Command]:
        # Add config, logfile, etc if it's the main command
        kls = deepcopy(cls)

        # allow with no explicit Config
        Config = cls.Config if hasattr(cls, "Config") else _empty

        kls.Config = add_missing_fields(
            deepcopy(Config), "logfile", str, default, "Path of run log"
        )
        return kls

    # "config_file", str, "config.toml", "Config file to use"

    def __init__(self) -> None:
        """
        Parse and validate settings on object instantiation

        `Command` configs are validated using Pydantic and `config` attribute is set
        with a `RuntimeConfig` generated from it.
        """

        # add missing fields if not specified by user. Methods using these are
        # classmethods so this must be done on the class and not the instance.
        if not hasattr(self.__class__, "Config"):
            self.__class__.Config = _empty

        super().__init__()
        if self.parent:
            return

        parser = self._populate_subcommands()

        args = parser.parse_args()
        config = vars(args)

        # Good-looking logging to console and file
        # FIXME how to handle config_file and logfile if not
        #   specified in the Command subclass config?
        if "logfile" in config:
            setup_logging(config["logfile"])

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
                # FIXME the special handling of "config_file" is really ugly
            }
            defaults.update(file_config)
            defaults.update(args_config)
            config = defaults
            config["config_file"] = path

        self._subcmd_to_run: list[Command] = [self]
        config = self.validate_config(config, self._subcmd_to_run)
        self.config: RuntimeConfig = make_namespace(config)

        try:
            # update logging configuration after having read the config file
            logging.getLogger().setLevel(self.config.logging.loglevel)
        except AttributeError:
            pass

    @property
    @classmethod
    def is_subcommand(cls):
        """
        Same as checking cls.parent
        """
        return cls.parent is not None

    @abc.abstractmethod
    def run(self, config: RuntimeConfig):
        """
        Function to run for the command
        """

    @classmethod
    def default_config(
        cls, _subcommand: Tuple[str, RuntimeConfig] | None = None, **kwargs
    ):
        """
        Get default config for command (and parents).

        To specify extra args use prefixes for parent commands:
            i.e. if you want to set a config for a `value` of a `sub` subcommand of a
            `com` command, use `com_sub_value` as key.
        """
        # get prefix from all parents names
        kls = cls
        parents = [kls]
        while kls.parent is not None:
            parents.append(kls.parent)
            kls = kls.parent
        parents.reverse()
        prefix = "_".join(map(lambda x: x.name, parents))
        if prefix:
            prefix = prefix + "_"

        relevant = {
            k.removeprefix(prefix): v for k, v in kwargs.items() if k.startswith(prefix)
        }

        config_dict = cls.Config(**relevant).dict()

        if _subcommand:
            config_dict[_subcommand[0]] = _subcommand[1]

        own_config = make_namespace(config_dict)

        if cls.parent:
            return cls.parent.default_config(
                _subcommand=(cls.name, own_config),
                **{k: v for k, v in kwargs.items() if not k.startswith(prefix)},
            )
        else:
            return own_config

    @classmethod
    def _populate_arguments(
        cls,
        *,
        parser: argparse.ArgumentParser,
        prefix="",
    ) -> argparse.ArgumentParser:
        """
        Create argparse ArgumentParser from model fields

        Args:
            parser: parser to use (means we're in a subparser)
        """
        # Add Pydantic model to an ArgumentParser
        if not hasattr(cls, "Config"):
            cls.Config = _empty
        fields = dataclass(cls.Config).__dataclass_fields__
        fields_detail = dataclass(cls.Config).__pydantic_fields__

        def parser_args(name, field) -> tuple[list, dict]:
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
                    "type": field.type if field.type in (int, float, str) else str,
                    "action": "append"
                    if field.type in (set[str], list[str])
                    else "store",
                    "default": field.default,
                    "help": fields_detail[field.name].description,
                },
            )

        # Turn the fields of the model as arguments of the parser
        for name, field in fields.items():
            # ignore fields not marked to be ignored in cli
            if (
                fields_detail[field.name].json_schema_extra
                and "cli" in fields_detail[field.name].json_schema_extra
                and not fields_detail[field.name].json_schema_extra["cli"]
            ):
                continue

            args, kwargs = parser_args(name, field)

            # booleans are special
            if field.type == bool:
                kwargs.pop("type")  # no type when using `store_true`
                kwargs["action"] = "store_true"

            parser.add_argument(
                *args,
                **kwargs,
            )
        return parser

    @classmethod
    def _populate_subcommands(cls, parser: argparse.ArgumentParser | None = None):
        """
        Add subcommands and relative arguments to argparse parser
        """
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
        """
        Parse and validate config.

        Command configs are validated using Pydantic and a dict is returned.
        """
        Config = TypeAdapter(cls.Config)

        # FIXME special handling for FieldInfo(s): crap code
        relevant = {k:v if not isinstance(v, FieldInfo) else v.default for k,v in relevant.items()}

        config = Config.validate_python(cls.Config(**relevant)).__dict__

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
                                cmd.name + "_"
                            ): v
                            for k, v in relevant.items()
                            if k.startswith(cmd.name + "_")
                            or k.startswith(f"{cls.name}_{cmd.name}_")
                        }
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
        """
        Call `cmd.run()` for each subcommand

        Should always be called on main command
        """
        if self.parent:
            raise RuntimeError("Run main command instead")

        for command in self._subcmd_to_run:
            logging.info("Running %s", command.name)
            command.run(self.config)


def arg(default, description, **kwargs):
    """
    Shortcut for pydantic.Field
    """
    return Field(default=default, description=description, json_schema_extra=kwargs)

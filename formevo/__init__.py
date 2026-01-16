# custom_addons/yonn_elearning_core/__init__.py
from . import controllers
from . import models
from . import wizard

from . import hooks

def configure_theme_automatically(env):
    """Configure automatiquement le thème après installation"""
    hooks.setup_theme_config(env)
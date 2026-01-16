from . import models
from . import wizards


def post_install_hook(env):
    """Hook post-installation pour initialiser données"""
    # Créer indicateurs par défaut
    env['quality.indicator'].search([]).unlink()  # Nettoyer si réinstall

    # Autres initialisations si nécessaire
    pass
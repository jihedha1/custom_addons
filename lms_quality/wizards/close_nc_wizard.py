# custom_addons/lms_quality/wizards/close_nc_wizard.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class CloseNCWizard(models.TransientModel):
    _name = 'quality.close.nc.wizard'  # ✅ CORRIGÉ : suppression du préfixe lms_quality
    _description = 'Assistant de clôture de non-conformité'

    non_conformity_id = fields.Many2one(
        'quality.non_conformity',
        string='Non-conformité',
        required=True,
        readonly=True
    )

    closure_notes = fields.Html(
        string='Notes de clôture',
        required=True,
        help='Résumé des actions menées et résultats obtenus'
    )

    effectiveness = fields.Selection([
        ('effective', 'Efficace'),
        ('partially_effective', 'Partiellement efficace'),
        ('not_effective', 'Non efficace'),
    ], string='Efficacité globale', required=True)

    preventive_actions = fields.Html(
        string='Actions préventives proposées',
        help='Mesures pour éviter la récurrence'
    )

    # ✅ AJOUTÉ : Champs supplémentaires pour conformité Qualiopi
    lessons_learned = fields.Html(
        string='Enseignements tirés',
        help='Ce qui a été appris de cette NC'
    )

    documentation_updated = fields.Boolean(
        string='Documentation mise à jour',
        help='Les procédures ont-elles été mises à jour?',
        default=False
    )

    communication_done = fields.Boolean(
        string='Communication effectuée',
        help='L\'équipe a-t-elle été informée?',
        default=False
    )

    # ✅ AJOUTÉ : Valeurs par défaut depuis contexte
    @api.model
    def default_get(self, fields_list):
        res = super(CloseNCWizard, self).default_get(fields_list)

        # Récupérer NC depuis contexte
        nc_id = self.env.context.get('active_id')
        if nc_id:
            nc = self.env['quality.non_conformity'].browse(nc_id)
            res['non_conformity_id'] = nc_id

            # ✅ AJOUTÉ : Vérifier état de la NC
            if nc.state != 'verification':
                raise UserError(
                    _("Seules les non-conformités en vérification peuvent être clôturées")
                )

        return res

    def action_close_nc(self):
        """Clôturer la non-conformité avec vérifications complètes"""
        self.ensure_one()

        # Vérifier que toutes les actions sont closes
        open_actions = self.non_conformity_id.corrective_action_ids.filtered(
            lambda a: a.state not in ['closed', 'cancelled']
        )

        if open_actions:
            raise ValidationError(
                _('Impossible de clôturer: %d action(s) corrective(s) encore ouverte(s).\n\nActions : %s') % (
                    len(open_actions),
                    ', '.join(open_actions.mapped('name'))
                )
            )

        # ✅ AJOUTÉ : Vérifier évaluation des actions
        uneval_actions = self.non_conformity_id.corrective_action_ids.filtered(
            lambda a: a.state == 'closed' and a.effectiveness == 'not_evaluated'
        )

        if uneval_actions:
            raise ValidationError(
                _("Certaines actions n'ont pas été évaluées : %s") % ', '.join(uneval_actions.mapped('name'))
            )

        # ✅ AJOUTÉ : Vérifier checklist Qualiopi
        if not self.documentation_updated:
            raise UserError(
                _("Vous devez confirmer que la documentation a été mise à jour")
            )

        if not self.communication_done:
            raise UserError(
                _("Vous devez confirmer que la communication a été effectuée")
            )

        # Mettre à jour la non-conformité
        self.non_conformity_id.write({
            'state': 'closed',
            'closure_date': fields.Date.today(),  # ✅ AJOUTÉ
        })

        # Créer message de clôture détaillé
        closure_message = self._prepare_closure_message()

        self.non_conformity_id.message_post(
            body=closure_message,
            subject=_('Clôture de la non-conformité'),
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )

        # ✅ AJOUTÉ : Archiver pièces jointes dans Documents si disponible
        if self.env['ir.module.module'].search([('name', '=', 'documents'), ('state', '=', 'installed')]):
            self._archive_to_documents()

        # ✅ AJOUTÉ : Notification au responsable
        self.non_conformity_id.activity_schedule(
            'mail.mail_activity_data_meeting',
            user_id=self.non_conformity_id.responsible_user_id.id,
            summary=_('NC clôturée - Revue à planifier'),
            note=_('La NC %s a été clôturée. Une revue d\'efficacité à 3 mois est recommandée.') %
                 self.non_conformity_id.name
        )

        # Retourner notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('✅ Non-conformité clôturée'),
                'message': _('La non-conformité %s a été clôturée avec succès.\n\nÉvaluation: %s') % (
                    self.non_conformity_id.name,
                    dict(self._fields['effectiveness'].selection).get(self.effectiveness)
                ),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def _prepare_closure_message(self):
        """Prépare le message HTML de clôture"""
        effectiveness_label = dict(self._fields['effectiveness'].selection).get(self.effectiveness)

        # ✅ AJOUTÉ : Statistiques des actions
        actions = self.non_conformity_id.corrective_action_ids
        total_actions = len(actions)
        effective_actions = len(actions.filtered(lambda a: a.effectiveness == 'effective'))

        message = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; background-color: #f8f9fa; border-radius: 5px;">
            <h2 style="color: #28a745; border-bottom: 2px solid #28a745; padding-bottom: 10px;">
                🎯 Clôture de la non-conformité
            </h2>

            <div style="background-color: white; padding: 15px; margin: 15px 0; border-left: 4px solid #28a745;">
                <h3 style="margin-top: 0;">Évaluation globale</h3>
                <p><strong>Efficacité globale:</strong> <span style="color: {'#28a745' if self.effectiveness == 'effective' else '#ffc107'}">{effectiveness_label}</span></p>
                <p><strong>Date de clôture:</strong> {fields.Date.today().strftime('%d/%m/%Y')}</p>
                <p><strong>Actions réalisées:</strong> {total_actions} dont {effective_actions} efficaces</p>
            </div>

            <div style="background-color: white; padding: 15px; margin: 15px 0;">
                <h3>📝 Notes de clôture</h3>
                {self.closure_notes}
            </div>

            {f'''
            <div style="background-color: white; padding: 15px; margin: 15px 0;">
                <h3>🛡️ Actions préventives proposées</h3>
                {self.preventive_actions}
            </div>
            ''' if self.preventive_actions else ''}

            {f'''
            <div style="background-color: white; padding: 15px; margin: 15px 0;">
                <h3>💡 Enseignements tirés</h3>
                {self.lessons_learned}
            </div>
            ''' if self.lessons_learned else ''}

            <div style="background-color: white; padding: 15px; margin: 15px 0; border-left: 4px solid #007bff;">
                <h3>✅ Checklist de clôture</h3>
                <ul style="list-style-type: none; padding-left: 0;">
                    <li>{'✅' if self.documentation_updated else '❌'} Documentation mise à jour</li>
                    <li>{'✅' if self.communication_done else '❌'} Communication effectuée</li>
                    <li>✅ Toutes les actions correctives clôturées</li>
                    <li>✅ Évaluation d'efficacité réalisée</li>
                </ul>
            </div>

            <div style="margin-top: 20px; padding: 10px; background-color: #d1ecf1; border-radius: 5px;">
                <p style="margin: 0; color: #0c5460;">
                    <strong>ℹ️ Prochaines étapes :</strong> Une revue d'efficacité à 3 mois est recommandée pour valider la pérennité des actions.
                </p>
            </div>
        </div>
        """

        return message

    def _archive_to_documents(self):
        """Archive les documents dans le module Documents"""
        # ✅ AJOUTÉ : Archivage automatique
        try:
            documents_folder = self.env['documents.folder'].search([
                ('name', '=', 'Non-conformités')
            ], limit=1)

            if not documents_folder:
                # Créer le dossier s'il n'existe pas
                documents_folder = self.env['documents.folder'].create({
                    'name': 'Non-conformités',
                    'description': 'Documents relatifs aux non-conformités',
                })

            # Créer un document de synthèse
            self.env['documents.document'].create({
                'name': f"Clôture NC {self.non_conformity_id.name}",
                'folder_id': documents_folder.id,
                'res_model': 'quality.non_conformity',
                'res_id': self.non_conformity_id.id,
            })
        except Exception as e:
            # Ne pas bloquer la clôture si l'archivage échoue
            _logger.warning(f"Erreur archivage documents: {e}")
# custom_addons/lms_public_kpi/models/public_kpi_snapshot.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, datetime, timedelta
import logging
import json
import base64

_logger = logging.getLogger(__name__)


class PublicKPISnapshot(models.Model):
    _name = 'public.kpi.snapshot'
    _description = 'Snapshot des indicateurs publics Qualiopi'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'publication_date desc, id desc'
    _rec_name = 'name'

    # ==========================================
    # CHAMPS DE BASE
    # ==========================================

    name = fields.Char(
        string='Titre',
        required=True,
        tracking=True,
        help="Titre du snapshot (ex: Indicateurs Q1 2024)"
    )

    # Statut avec states pour workflow
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('review', 'En révision'),  # ✅ AJOUT étape intermédiaire
        ('published', 'Publié'),
        ('archived', 'Archivé'),
    ], string='Statut',
        default='draft',
        required=True,
        tracking=True,
        help="État du snapshot dans le workflow de publication")

    # ==========================================
    # PÉRIODE DE RÉFÉRENCE
    # ==========================================

    period_type = fields.Selection([
        ('monthly', 'Mensuel'),
        ('quarterly', 'Trimestriel'),
        ('semiannual', 'Semestriel'),
        ('annual', 'Annuel'),
        ('custom', 'Personnalisé'),
    ], string='Type de période',
        default='quarterly',
        required=True,
        tracking=True,
        help="Périodicité de publication des indicateurs")

    period_start = fields.Date(
        string='Début de période',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        help="Date de début de la période mesurée"
    )

    period_end = fields.Date(
        string='Fin de période',
        required=True,
        tracking=True,
        help="Date de fin de la période mesurée"
    )

    # ✅ AJOUT : Durée calculée automatiquement
    period_duration = fields.Integer(
        string='Durée (jours)',
        compute='_compute_period_duration',
        store=True,
        help="Nombre de jours de la période"
    )

    # ==========================================
    # DATES DE GESTION
    # ==========================================

    publication_date = fields.Date(
        string='Date de publication',
        readonly=True,
        tracking=True,
        help="Date effective de publication du snapshot"
    )

    next_update_date = fields.Date(
        string='Prochaine mise à jour prévue',
        tracking=True,
        help="Date planifiée pour la prochaine publication"
    )

    # ✅ AJOUT : Date de révision
    review_date = fields.Date(
        string='Date de révision',
        readonly=True,
        tracking=True,
        help="Date de passage en révision"
    )

    # ✅ AJOUT : Date d'archivage
    archive_date = fields.Date(
        string='Date d\'archivage',
        readonly=True,
        tracking=True,
        help="Date d'archivage du snapshot"
    )

    # ==========================================
    # RELATIONS
    # ==========================================

    kpi_version_ids = fields.One2many(
        'public.kpi.version',
        'snapshot_id',
        string='Indicateurs',
        tracking=True
    )

    # ✅ AJOUT : Lien vers snapshot précédent
    previous_snapshot_id = fields.Many2one(
        'public.kpi.snapshot',
        string='Snapshot précédent',
        help="Lien vers le snapshot de la période précédente",
        domain=[('state', '=', 'published')]
    )

    # ✅ AJOUT : Snapshots suivants
    next_snapshot_ids = fields.One2many(
        'public.kpi.snapshot',
        'previous_snapshot_id',
        string='Snapshots suivants',
        help="Snapshots créés après celui-ci"
    )

    # ==========================================
    # MÉTRIQUES CALCULÉES
    # ==========================================

    kpi_count = fields.Integer(
        string='Nombre d\'indicateurs',
        compute='_compute_kpi_metrics',
        store=True
    )

    published_kpi_count = fields.Integer(
        string='Indicateurs publiés',
        compute='_compute_kpi_metrics',
        store=True
    )

    # ✅ AJOUT : Taux de complétion
    completion_rate = fields.Float(
        string='Taux de complétion (%)',
        compute='_compute_kpi_metrics',
        store=True,
        help="Pourcentage d'indicateurs avec valeur"
    )

    # ✅ AJOUT : Moyenne des KPI
    average_kpi_value = fields.Float(
        string='Moyenne des indicateurs',
        compute='_compute_average_kpi',
        store=True,
        digits=(5, 2),
        help="Valeur moyenne de tous les indicateurs (en %)"
    )

    # ==========================================
    # SOURCE DES DONNÉES
    # ==========================================

    data_source = fields.Selection([
        ('manual', 'Saisie manuelle'),
        ('auto_calculated', 'Calcul automatique'),
        ('mixed', 'Mixte'),
        ('external', 'Source externe'),  # ✅ AJOUT
    ], string='Source des données',
        default='manual',
        tracking=True,
        help="Origine des données des indicateurs")

    # ✅ AJOUT : Détails source externe
    external_source_url = fields.Char(
        string='URL source externe',
        help="Lien vers la source externe des données"
    )

    # ==========================================
    # NOTES & COMMENTAIRES
    # ==========================================

    notes = fields.Text(
        string='Notes internes',
        help='Commentaires internes non visibles publiquement'
    )

    public_notes = fields.Html(
        string='Notes publiques',
        help='Commentaires affichés avec les indicateurs sur le site web'
    )

    # ✅ AJOUT : Méthodologie détaillée
    methodology = fields.Html(
        string='Méthodologie de calcul',
        help='Explication détaillée de la méthodologie utilisée pour calculer les indicateurs'
    )

    # ==========================================
    # PIÈCES JOINTES
    # ==========================================

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'kpi_snapshot_attachment_rel',
        'snapshot_id',
        'attachment_id',
        string='Documents justificatifs'
    )

    # ✅ AJOUT : Nombre de pièces jointes
    attachment_count = fields.Integer(
        string='Nombre de documents',
        compute='_compute_attachment_count'
    )

    # ==========================================
    # URL PUBLIQUE
    # ==========================================

    public_url = fields.Char(
        string='URL publique',
        compute='_compute_public_url',
        store=True,
        help="URL d'accès public au snapshot"
    )

    # ✅ AJOUT : QR Code pour accès mobile
    qr_code = fields.Binary(
        string='QR Code',
        compute='_compute_qr_code',
        help="QR Code pour accès rapide depuis mobile"
    )

    # ==========================================
    # TRAÇABILITÉ
    # ==========================================

    version_count = fields.Integer(
        string='Nombre de versions',
        compute='_compute_version_count',
        store=True
    )

    # ✅ AJOUT : Utilisateur validateur
    validator_id = fields.Many2one(
        'res.users',
        string='Validé par',
        readonly=True,
        tracking=True,
        help="Utilisateur ayant validé le snapshot"
    )

    # ✅ AJOUT : Date de dernière modification
    last_modification_date = fields.Datetime(
        string='Dernière modification',
        compute='_compute_last_modification',
        store=True,
        help="Date et heure de la dernière modification"
    )

    # ✅ AJOUT : Nombre de consultations
    view_count = fields.Integer(
        string='Nombre de vues',
        default=0,
        help="Nombre de fois que le snapshot a été consulté"
    )

    # ✅ AJOUT : Dernière consultation
    last_view_date = fields.Datetime(
        string='Dernière consultation',
        help="Date et heure de la dernière consultation publique"
    )

    # ==========================================
    # ALERTES & NOTIFICATIONS
    # ==========================================

    # ✅ AJOUT : Alerte mise à jour dépassée
    update_alert = fields.Boolean(
        string='Alerte mise à jour',
        compute='_compute_update_alert',
        help="Indique si la date de mise à jour est dépassée"
    )

    # ✅ AJOUT : Nombre de jours de retard
    days_overdue = fields.Integer(
        string='Jours de retard',
        compute='_compute_update_alert',
        help="Nombre de jours depuis la date de mise à jour prévue"
    )

    # ==========================================
    # STATISTIQUES AVANCÉES
    # ==========================================

    # ✅ AJOUT : Évolution globale vs période précédente
    global_evolution_rate = fields.Float(
        string='Évolution globale (%)',
        compute='_compute_global_evolution',
        store=True,
        digits=(5, 2),
        help="Évolution moyenne de tous les indicateurs vs période précédente"
    )

    # ==========================================
    # MÉTHODES COMPUTE
    # ==========================================

    @api.depends('period_start', 'period_end')
    def _compute_period_duration(self):
        """Calcule la durée de la période en jours"""
        for snapshot in self:
            if snapshot.period_start and snapshot.period_end:
                delta = snapshot.period_end - snapshot.period_start
                snapshot.period_duration = delta.days + 1
            else:
                snapshot.period_duration = 0

    @api.depends('kpi_version_ids', 'kpi_version_ids.state', 'kpi_version_ids.value')
    def _compute_kpi_metrics(self):
        """Calcule les métriques sur les KPI"""
        for snapshot in self:
            kpis = snapshot.kpi_version_ids
            total = len(kpis)
            published = len(kpis.filtered(lambda k: k.state == 'published'))
            with_value = len(kpis.filtered(lambda k: k.value and k.value > 0))

            snapshot.kpi_count = total
            snapshot.published_kpi_count = published
            snapshot.completion_rate = (with_value / total * 100) if total > 0 else 0

    @api.depends('kpi_version_ids.value')
    def _compute_average_kpi(self):
        """Calcule la moyenne des valeurs KPI"""
        for snapshot in self:
            kpis_with_value = snapshot.kpi_version_ids.filtered(
                lambda k: k.value and k.value > 0 and k.unit == '%'
            )
            if kpis_with_value:
                total_value = sum(kpis_with_value.mapped('value'))
                snapshot.average_kpi_value = total_value / len(kpis_with_value)
            else:
                snapshot.average_kpi_value = 0.0

    @api.depends('state')  # ✅ CORRECTION : Seulement 'state', pas 'id'
    def _compute_public_url(self):
        """Calcule l'URL publique du snapshot"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        for snapshot in self:
            if snapshot.id and snapshot.state == 'published':
                snapshot.public_url = f"{base_url}/kpis/snapshot/{snapshot.id}"
            else:
                snapshot.public_url = False

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        """Compte les pièces jointes"""
        for snapshot in self:
            snapshot.attachment_count = len(snapshot.attachment_ids)

    @api.depends('public_url')
    def _compute_qr_code(self):
        """Génère un QR Code pour l'URL publique"""
        for snapshot in self:
            if snapshot.public_url:
                try:
                    import qrcode
                    import io
                    import base64

                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(snapshot.public_url)
                    qr.make(fit=True)

                    img = qr.make_image(fill_color="black", back_color="white")
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')

                    snapshot.qr_code = base64.b64encode(buffer.getvalue())
                except ImportError:
                    _logger.warning("Module qrcode non installé. QR Code non généré.")
                    snapshot.qr_code = False
            else:
                snapshot.qr_code = False

    @api.depends('write_date')
    def _compute_last_modification(self):
        """Calcule la date de dernière modification"""
        for snapshot in self:
            snapshot.last_modification_date = snapshot.write_date or snapshot.create_date

    @api.depends('next_update_date')
    def _compute_update_alert(self):
        """Vérifie si la mise à jour est en retard"""
        today = fields.Date.today()
        for snapshot in self:
            if snapshot.next_update_date and snapshot.state == 'published':
                if snapshot.next_update_date < today:
                    snapshot.update_alert = True
                    delta = today - snapshot.next_update_date
                    snapshot.days_overdue = delta.days
                else:
                    snapshot.update_alert = False
                    snapshot.days_overdue = 0
            else:
                snapshot.update_alert = False
                snapshot.days_overdue = 0

    @api.depends('previous_snapshot_id', 'kpi_version_ids.evolution_rate')
    def _compute_global_evolution(self):
        """Calcule l'évolution globale vs snapshot précédent"""
        for snapshot in self:
            kpis_with_evolution = snapshot.kpi_version_ids.filtered(
                lambda k: k.evolution_rate != 0
            )
            if kpis_with_evolution:
                total_evolution = sum(kpis_with_evolution.mapped('evolution_rate'))
                snapshot.global_evolution_rate = total_evolution / len(kpis_with_evolution)
            else:
                snapshot.global_evolution_rate = 0.0

    @api.depends('kpi_version_ids')
    def _compute_version_count(self):
        """Compte les versions d'indicateurs"""
        for snapshot in self:
            snapshot.version_count = len(snapshot.kpi_version_ids)

    # ==========================================
    # CONTRAINTES
    # ==========================================

    @api.constrains('period_start', 'period_end')
    def _check_period(self):
        """Vérifie la cohérence des dates de période"""
        for snapshot in self:
            if snapshot.period_end <= snapshot.period_start:
                raise ValidationError(_(
                    "La date de fin de période (%s) doit être postérieure à la date de début (%s)."
                ) % (snapshot.period_end, snapshot.period_start))

    @api.constrains('next_update_date')
    def _check_next_update(self):
        """Avertissement si date de mise à jour dans le passé"""
        for snapshot in self:
            if snapshot.next_update_date and snapshot.next_update_date < date.today():
                _logger.warning(
                    "⚠️  Date de prochaine mise à jour dans le passé pour snapshot #%s (%s): %s",
                    snapshot.id,
                    snapshot.name,
                    snapshot.next_update_date
                )

    @api.constrains('previous_snapshot_id')
    def _check_previous_snapshot(self):
        """Évite les références circulaires"""
        for snapshot in self:
            if snapshot.previous_snapshot_id:
                # Vérifier que le snapshot précédent n'est pas le même
                if snapshot.previous_snapshot_id.id == snapshot.id:
                    raise ValidationError(_("Un snapshot ne peut pas être son propre prédécesseur."))

                # Vérifier que le snapshot précédent est publié
                if snapshot.previous_snapshot_id.state != 'published':
                    raise ValidationError(_(
                        "Le snapshot précédent doit être publié. "
                        "Snapshot sélectionné: %s (état: %s)"
                    ) % (
                                              snapshot.previous_snapshot_id.name,
                                              dict(snapshot._fields['state'].selection)[
                                                  snapshot.previous_snapshot_id.state]
                                          ))

    # Contrainte SQL pour unicité du nom par période
    _sql_constraints = [
        ('name_period_unique',
         'UNIQUE(name, period_start, period_end)',
         'Un snapshot avec ce nom existe déjà pour cette période.'),
    ]

    # ==========================================
    # ACTIONS PRINCIPALES
    # ==========================================

    def action_submit_for_review(self):
        """Soumettre le snapshot pour révision"""
        for snapshot in self:
            # Validation préalable
            validation = snapshot._validate_for_publication()
            if not validation['valid']:
                raise UserError(_(
                    "Le snapshot ne peut pas être soumis pour révision:\n%s"
                ) % '\n'.join(f"• {err}" for err in validation['errors']))

            # Passage en révision
            snapshot.write({
                'state': 'review',
                'review_date': fields.Date.today(),
            })

            # Créer activité pour manager
            managers = self.env.ref('lms_public_kpi.group_kpi_manager').users
            if managers:
                snapshot.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=managers[0].id,
                    summary=_('📋 Révision snapshot KPI : %s') % snapshot.name,
                    note=_(
                        'Le snapshot "%s" est prêt pour révision.\n\n'
                        'Période: %s → %s\n'
                        'Indicateurs: %d\n'
                        'Taux de complétion: %.1f%%\n\n'
                        'Veuillez valider ou rejeter ce snapshot.'
                    ) % (
                             snapshot.name,
                             snapshot.period_start,
                             snapshot.period_end,
                             snapshot.kpi_count,
                             snapshot.completion_rate
                         )
                )

            snapshot.message_post(
                body=_('Snapshot soumis pour révision par %s') % self.env.user.name,
                message_type='notification'
            )

            _logger.info("✅ Snapshot #%s soumis pour révision", snapshot.id)

    def action_reject(self):
        """Rejeter le snapshot et retour en brouillon"""
        for snapshot in self:
            if snapshot.state != 'review':
                raise UserError(_("Seuls les snapshots en révision peuvent être rejetés."))

            # Demander une raison
            return {
                'name': _('Rejeter le snapshot'),
                'type': 'ir.actions.act_window',
                'res_model': 'kpi.rejection.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_snapshot_id': snapshot.id}
            }

    def action_publish(self):
        """Publier le snapshot avec validation complète"""
        for snapshot in self:
            # Vérifications d'état
            if snapshot.state not in ['review', 'draft']:
                raise UserError(_(
                    "Seuls les snapshots en révision ou en brouillon peuvent être publiés. "
                    "État actuel: %s"
                ) % dict(snapshot._fields['state'].selection)[snapshot.state])

            # Validation complète
            validation = snapshot._validate_for_publication()
            if not validation['valid']:
                raise UserError(_(
                    "Le snapshot ne peut pas être publié:\n%s"
                ) % '\n'.join(f"• {err}" for err in validation['errors']))

            # Dépublier le snapshot actuel de la même période si existe
            existing_published = self.search([
                ('id', '!=', snapshot.id),
                ('state', '=', 'published'),
                ('period_start', '=', snapshot.period_start),
                ('period_end', '=', snapshot.period_end),
            ])

            if existing_published:
                _logger.info(
                    "Archivage automatique du snapshot #%s pour republication",
                    existing_published.id
                )
                existing_published.action_archive()

            # Publication
            snapshot.write({
                'state': 'published',
                'publication_date': fields.Date.today(),
                'validator_id': self.env.user.id,
            })

            # Publier tous les indicateurs
            snapshot.kpi_version_ids.write({'state': 'published'})

            # Traçabilité Qualiopi
            snapshot.message_post(
                body=_(
                    '✅ <strong>Snapshot publié</strong><br/>'
                    'Date: %s<br/>'
                    'Validé par: %s<br/>'
                    'Indicateurs publiés: %d<br/>'
                    'Taux de complétion: %.1f%%<br/>'
                    'URL publique: <a href="%s" target="_blank">%s</a>'
                ) % (
                         fields.Date.today(),
                         self.env.user.name,
                         snapshot.published_kpi_count,
                         snapshot.completion_rate,
                         snapshot.public_url,
                         snapshot.public_url
                     ),
                message_type='notification',
                subtype_id=self.env.ref('mail.mt_note').id
            )

            _logger.info(
                "✅ Snapshot #%s publié : %s (%d indicateurs, %.1f%% complétion)",
                snapshot.id,
                snapshot.name,
                snapshot.published_kpi_count,
                snapshot.completion_rate
            )

            # Notification email aux abonnés
            snapshot._send_publication_notification()

    # ==========================================
    # MÉTHODES UTILITAIRES
    # ==========================================

    def _validate_for_publication(self):
        """Valide qu'un snapshot est prêt pour publication"""
        self.ensure_one()

        errors = []
        warnings = []

        # Vérifier indicateurs
        if not self.kpi_version_ids:
            errors.append(_("Aucun indicateur défini"))

        # Vérifier valeurs
        invalid_kpis = self.kpi_version_ids.filtered(
            lambda k: not k.value or k.value <= 0
        )
        if invalid_kpis:
            errors.append(_(
                "%d indicateur(s) sans valeur: %s"
            ) % (len(invalid_kpis), ', '.join(invalid_kpis.mapped('name'))))

        # Vérifier période
        if self.period_end <= self.period_start:
            errors.append(_("Période invalide (fin <= début)"))

        # Vérifier complétion
        if self.completion_rate < 80:
            warnings.append(_(
                "Taux de complétion faible: %.1f%% (recommandé: >80%%)"
            ) % self.completion_rate)

        # Vérifier catégories
        categories_used = self.kpi_version_ids.mapped('category_id')
        if len(categories_used) < 3:
            warnings.append(_(
                "Seulement %d catégorie(s) utilisée(s) (recommandé: ≥3)"
            ) % len(categories_used))

        # Vérifier notes publiques
        if not self.public_notes:
            warnings.append(_("Aucune note publique définie"))

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'completion_rate': self.completion_rate,
        }

    def action_export_audit_proof(self):
        """Générer preuve d'audit JSON conforme Qualiopi"""
        self.ensure_one()

        data = {
            'snapshot': {
                'id': self.id,
                'name': self.name,
                'period': {
                    'type': self.period_type,
                    'start': str(self.period_start),
                    'end': str(self.period_end),
                    'duration_days': self.period_duration,
                },
                'publication': {
                    'date': str(self.publication_date) if self.publication_date else None,
                    'validator': self.validator_id.name if self.validator_id else None,
                    'state': self.state,
                },
                'url': self.public_url,
                'metrics': {
                    'kpi_count': self.kpi_count,
                    'published_kpi_count': self.published_kpi_count,
                    'completion_rate': round(self.completion_rate, 2),
                    'average_value': round(self.average_kpi_value, 2),
                    'global_evolution': round(self.global_evolution_rate, 2),
                },
            },
            'kpis': [],
            'metadata': {
                'exported_at': str(fields.Datetime.now()),
                'exported_by': self.env.user.name,
                'source': 'Odoo LMS - Certification Qualiopi',
                'version': '17.0.1.0.0',
            }
        }

        # Ajouter indicateurs
        for kpi in self.kpi_version_ids.filtered(lambda k: k.state == 'published').sorted('sequence'):
            data['kpis'].append({
                'id': kpi.id,
                'name': kpi.name,
                'category': {
                    'name': kpi.category_id.name,
                    'code': kpi.category_id.code,
                },
                'value': round(float(kpi.value), 2) if kpi.value else 0,
                'unit': kpi.unit or '',
                'evolution': {
                    'rate': round(float(kpi.evolution_rate), 2) if kpi.evolution_rate else 0,
                    'direction': kpi.evolution_direction or 'stable',
                    'previous_value': round(float(kpi.previous_value), 2) if kpi.previous_value else None,
                },
                'description': kpi.description or '',
                'calculation': {
                    'method': kpi.calculation_method,
                    'last_date': str(kpi.last_calculation_date) if kpi.last_calculation_date else None,
                },
            })

        # Créer attachment JSON
        json_data = json.dumps(data, indent=2, ensure_ascii=False)

        attachment = self.env['ir.attachment'].create({
            'name': f'Audit_KPI_Qualiopi_{self.name.replace(" ", "_")}_{fields.Date.today()}.json',
            'datas': base64.b64encode(json_data.encode()),
            'res_model': 'public.kpi.snapshot',
            'res_id': self.id,
            'mimetype': 'application/json',
            'description': _(
                'Export audit Qualiopi - Indicateurs publics\n'
                'Période: %s → %s\n'
                'Date export: %s'
            ) % (self.period_start, self.period_end, fields.Datetime.now()),
        })

        # Message traçabilité
        self.message_post(
            body=_('📄 Export audit généré : <a href="/web/content/%s?download=true">%s</a>') % (
                attachment.id,
                attachment.name
            ),
            message_type='notification'
        )

        _logger.info("📄 Export audit créé: attachment #%s", attachment.id)

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_increment_view_count(self):
        """Incrémenter le compteur de vues (appelé depuis controller)"""
        self.ensure_one()
        self.sudo().write({
            'view_count': self.view_count + 1,
            'last_view_date': fields.Datetime.now(),
        })

    def _send_publication_notification(self):
        """Envoyer notification email lors de la publication"""
        self.ensure_one()

        # Récupérer abonnés du snapshot
        followers = self.message_follower_ids.mapped('partner_id')

        if not followers:
            return

        # Créer template email
        template = self.env.ref('lms_public_kpi.email_template_kpi_publication', raise_if_not_found=False)

        if template:
            template.send_mail(self.id, force_send=True)
            _logger.info(
                "📧 Notification publication envoyée à %d destinataire(s)",
                len(followers)
            )

    def action_view_kpis(self):
        """Action pour voir les KPI du snapshot"""
        self.ensure_one()
        return {
            'name': _('Indicateurs - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'public.kpi.version',
            'view_mode': 'tree,form',
            'domain': [('snapshot_id', '=', self.id)],
            'context': {
                'default_snapshot_id': self.id,
                'search_default_published': 1,
            }
        }

    def action_view_attachments(self):
        """Action pour voir les pièces jointes"""
        self.ensure_one()
        return {
            'name': _('Documents - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,tree,form',
            'domain': [
                '|',
                '&', ('res_model', '=', 'public.kpi.snapshot'), ('res_id', '=', self.id),
                ('id', 'in', self.attachment_ids.ids),
            ],
            'context': {
                'default_res_model': 'public.kpi.snapshot',
                'default_res_id': self.id,
            }
        }

    # ==========================================
    # MÉTHODES ONCHANGE
    # ==========================================

    @api.onchange('period_type')
    def _onchange_period_type(self):
        """Suggérer dates en fonction du type de période"""
        if self.period_type and self.period_start:
            if self.period_type == 'monthly':
                # Fin du mois
                from calendar import monthrange
                year, month = self.period_start.year, self.period_start.month
                last_day = monthrange(year, month)[1]
                self.period_end = date(year, month, last_day)

            elif self.period_type == 'quarterly':
                self.period_end = self.period_start + timedelta(days=89)

            elif self.period_type == 'semiannual':
                self.period_end = self.period_start + timedelta(days=179)

            elif self.period_type == 'annual':
                year = self.period_start.year
                self.period_end = date(year, 12, 31)

    @api.onchange('period_end')
    def _onchange_period_end(self):
        """Suggérer date de prochaine mise à jour et vérifier les chevauchements"""
        result = {}

        for record in self:
            if record.period_end and not record.next_update_date:
                # Suggérer 15 jours après la fin de période
                record.next_update_date = record.period_end + timedelta(days=15)

            # Vérifier les chevauchements avec les snapshots publiés existants
            if record.period_end and record.period_start:
                existing_published = self.env['public.kpi.snapshot'].search([
                    ('state', '=', 'published'),
                    ('id', '!=', record.id),  # Exclure l'enregistrement actuel
                    ('period_start', '<=', record.period_end),
                    ('period_end', '>=', record.period_start)
                ], limit=1)

                if existing_published:
                    warning = {
                        'title': _('Période chevauchante'),
                        'message': _(
                            "Un snapshot publié existe déjà pour cette période : %s "
                            "(%s - %s). "
                            "ID: %d"
                        ) % (
                                       existing_published.name,
                                       existing_published.period_start,
                                       existing_published.period_end,
                                       existing_published.id
                                   )
                    }
                    result['warning'] = warning

        return result

    def action_open_public_url(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.public_url,
            'target': 'new',
        }
    def action_archive(self):
        """Archiver le snapshot"""
        for snapshot in self:
            snapshot.write({
                'state': 'archived',
                'archive_date': fields.Date.today(),
            })

            snapshot.message_post(
                body=_('Snapshot archivé par %s') % self.env.user.name,
                message_type='notification'
            )

            _logger.info("📦 Snapshot #%s archivé", snapshot.id)


    def action_unarchive(self):
        """Désarchiver le snapshot"""
        for snapshot in self:
            snapshot.write({
                'state': 'draft',
                'archive_date': False,
            })

            snapshot.message_post(body=_('Snapshot réactivé'))
            _logger.info("📂 Snapshot #%s réactivé", snapshot.id)


    def action_duplicate(self):
        """Dupliquer le snapshot avec ses indicateurs"""
        self.ensure_one()

        # Nom du nouveau snapshot
        new_name = _("%s (Copie)") % self.name

        # Calculer nouvelle période (suggestion)
        if self.period_type == 'monthly':
            delta = timedelta(days=30)
        elif self.period_type == 'quarterly':
            delta = timedelta(days=90)
        elif self.period_type == 'semiannual':
            delta = timedelta(days=180)
        elif self.period_type == 'annual':
            delta = timedelta(days=365)
        else:
            delta = timedelta(days=self.period_duration)

        new_start = self.period_end + timedelta(days=1)
        new_end = new_start + delta - timedelta(days=1)

        # Créer nouveau snapshot
        new_snapshot = self.copy({
            'name': new_name,
            'state': 'draft',
            'publication_date': False,
            'review_date': False,
            'archive_date': False,
            'validator_id': False,
            'next_update_date': False,
            'period_start': new_start,
            'period_end': new_end,
            'previous_snapshot_id': self.id,  # Lien vers snapshot source
            'view_count': 0,
            'last_view_date': False,
        })

        # Dupliquer les indicateurs avec historique
        for kpi in self.kpi_version_ids:
            kpi.copy({
                'snapshot_id': new_snapshot.id,
                'state': 'draft',
                'previous_value': kpi.value,  # Conserver historique
                'value': 0,  # Réinitialiser valeur
                'last_calculation_date': False,
            })

        _logger.info(
            "📋 Snapshot #%s dupliqué → #%s (%s)",
            self.id,
            new_snapshot.id,
            new_snapshot.name
        )

        # Message de confirmation
        self.message_post(
            body=_('Snapshot dupliqué → <a href="#id=%s&model=public.kpi.snapshot">%s</a>') % (
                new_snapshot.id,
                new_snapshot.name
            )
        )

        # Rediriger vers le nouveau snapshot
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'public.kpi.snapshot',
            'res_id': new_snapshot.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_state': 'draft'}
        }


    def action_calculate_kpis(self):
        """Calculer automatiquement tous les indicateurs"""
        for snapshot in self:
            calculated = 0
            errors = []

            for kpi in snapshot.kpi_version_ids:
                if kpi.calculation_method != 'manual':
                    try:
                        kpi.action_calculate()
                        calculated += 1
                    except Exception as e:
                        errors.append(f"{kpi.name}: {str(e)}")
                        _logger.error("❌ Erreur calcul KPI %s: %s", kpi.name, str(e))

            # Message de résultat
            if calculated > 0:
                snapshot.message_post(
                    body=_('✅ %d indicateur(s) calculé(s) automatiquement') % calculated,
                    message_type='notification'
                )

            if errors:
                snapshot.message_post(
                    body=_('❌ Erreurs de calcul:\n%s') % '\n'.join(f'• {e}' for e in errors),
                    message_type='notification'
                )

            _logger.info(
                "🔢 Calcul KPI snapshot #%s: %d OK, %d erreurs",
                snapshot.id,
                calculated,
                len(errors)
            )


    # ==========================================
    # MÉTHODES CRON
    # ==========================================

    @api.model
    def _cron_check_upcoming_updates(self):
        """Vérifier les mises à jour à venir et créer des activités"""
        today = fields.Date.today()
        warning_days = 7  # Alerte 7 jours avant

        # Snapshots nécessitant une mise à jour
        upcoming = self.search([
            ('state', '=', 'published'),
            ('next_update_date', '<=', today + timedelta(days=warning_days)),
            ('next_update_date', '>=', today),
        ])

        for snapshot in upcoming:
            # Vérifier si activité existe déjà
            existing_activity = self.env['mail.activity'].search([
                ('res_model', '=', 'public.kpi.snapshot'),
                ('res_id', '=', snapshot.id),
                ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
                ('summary', 'ilike', 'Mise à jour KPI'),
                ('date_deadline', '>=', today),
            ], limit=1)

            if not existing_activity:
                days_until = (snapshot.next_update_date - today).days

                snapshot.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=snapshot.create_uid.id,
                    summary=_('📊 Mise à jour KPI à venir : %s') % snapshot.name,
                    note=_(
                        'La mise à jour prévue approche dans %d jours (%s).\n\n'
                        'Actions à effectuer:\n'
                        '• Collecter les nouvelles données\n'
                        '• Créer le nouveau snapshot\n'
                        '• Calculer les indicateurs\n'
                        '• Soumettre pour révision\n\n'
                        'Période actuelle: %s → %s'
                    ) % (
                             days_until,
                             snapshot.next_update_date,
                             snapshot.period_start,
                             snapshot.period_end
                         ),
                    date_deadline=snapshot.next_update_date
                )

                _logger.info(
                    "📅 Activité créée pour snapshot #%s (mise à jour dans %d jours)",
                    snapshot.id,
                    days_until
                )

        # Snapshots en retard
        overdue = self.search([
            ('state', '=', 'published'),
            ('next_update_date', '<', today),
        ])

        for snapshot in overdue:
            if not snapshot.update_alert:
                continue

            # Activité urgente
            existing_urgent = self.env['mail.activity'].search([
                ('res_model', '=', 'public.kpi.snapshot'),
                ('res_id', '=', snapshot.id),
                ('activity_type_id', '=', self.env.ref('mail.mail_activity_data_todo').id),
                ('summary', 'ilike', 'URGENT'),
            ], limit=1)

            if not existing_urgent:
                snapshot.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=snapshot.create_uid.id,
                    summary=_('🚨 URGENT - Mise à jour KPI en retard : %s') % snapshot.name,
                    note=_(
                        '⚠️ La mise à jour prévue est dépassée de %d jours !\n\n'
                        'Date prévue: %s\n'
                        'Aujourd\'hui: %s\n\n'
                        'Action immédiate requise pour maintenir la conformité Qualiopi.'
                    ) % (
                             snapshot.days_overdue,
                             snapshot.next_update_date,
                             today
                         ),
                    date_deadline=today
                )

                _logger.warning(
                    "🚨 Alerte retard snapshot #%s : %d jours",
                    self.id,
                    self.days_overdue
                )

        return True

    # ==========================================
    # CHAMPS POUR LES LABELS DANS LE TEMPLATE
    # ==========================================

    period_type_label = fields.Char(
        string='Type de période (texte)',
        compute='_compute_type_labels',
        store=False
    )

    data_source_label = fields.Char(
        string='Source données (texte)',
        compute='_compute_type_labels',
        store=False
    )

    @api.depends('period_type', 'data_source')
    def _compute_type_labels(self):
        """Calcule les libellés textuels des champs de sélection"""
        for record in self:
            # Pour period_type
            period_field = self.env['public.kpi.snapshot']._fields.get('period_type')
            if period_field and record.period_type:
                selection_dict = dict(period_field.selection)
                record.period_type_label = selection_dict.get(record.period_type, record.period_type)
            else:
                record.period_type_label = ''

            # Pour data_source
            source_field = self.env['public.kpi.snapshot']._fields.get('data_source')
            if source_field and record.data_source:
                selection_dict = dict(source_field.selection)
                record.data_source_label = selection_dict.get(record.data_source, record.data_source)
            else:
                record.data_source_label = ''

# custom_addons/lms_public_info/controllers/main.py
# -*- coding: utf-8 -*-
import logging
import datetime
import re
from odoo import http, _, api
from odoo.http import request

_logger = logging.getLogger(__name__)


class PublicInfoWebsiteController(http.Controller):

    @http.route('/formation-details/<model("slide.channel"):channel>', type='http', auth='public', website=True)
    def formation_detail(self, channel, **kwargs):
        """Page détaillée d'une formation"""
        if not channel.is_published:
            return request.not_found()

        return request.render('lms_public_info.formation_public_page', {
            'channel': channel,
            'main_object': channel,
        })

    @http.route('/formations/catalogue', type='http', auth='public', website=True)
    def formation_catalogue(self, **kwargs):
        """Catalogue des formations publiées"""
        domain = [
            ('is_published', '=', True),
            ('publication_ready', '=', True),
        ]

        # Filtres
        modality = kwargs.get('modality')
        if modality:
            domain.append(('training_modality', '=', modality))

        # CORRECTION : Utiliser difficulty_level au lieu de difficulty_level
        difficulty = kwargs.get('difficulty')
        if difficulty:
            domain.append(('difficulty_level', '=', difficulty))  # CORRECTION ICI

        training_type = kwargs.get('training_type')
        if training_type:
            domain.append(('training_type', '=', training_type))

        # Recherche
        search = kwargs.get('search')
        if search:
            domain.append('|')
            domain.append(('name', 'ilike', search))
            domain.append(('description', 'ilike', search))

        channels = request.env['slide.channel'].sudo().search(domain, order='sequence')

        return request.render('lms_public_info.formation_catalogue_page', {
            'channels': channels,
            'search': search,
            'modality': modality,
            'difficulty': difficulty,  # CORRECTION : Renommer ici aussi si besoin
            'training_type': training_type,
        })

    @http.route('/formation/rdv/<int:channel_id>', type='http', auth='public', website=True)
    def formation_appointment(self, channel_id, **kwargs):
        """Page de prise de rendez-vous pour une formation"""
        channel = request.env['slide.channel'].sudo().browse(channel_id)

        if not channel.exists() or not channel.is_published:
            return request.not_found()

        if not channel.appointment_available:
            return request.redirect(f'/formation/rdv/unavailable/{channel_id}')

        return request.render('lms_public_info.formation_appointment_page', {
            'channel': channel,
        })

    @http.route('/formation/rdv/unavailable/<int:channel_id>', type='http', auth='public', website=True)
    def formation_appointment_unavailable(self, channel_id, **kwargs):
        """Page quand les rendez-vous ne sont pas disponibles"""
        channel = request.env['slide.channel'].sudo().browse(channel_id)

        if not channel.exists() or not channel.is_published:
            return request.not_found()

        return request.render('lms_public_info.formation_appointment_unavailable', {
            'channel': channel,
        })

    @http.route('/formation/rdv/submit', type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def formation_rdv_submit(self, **post):
        """
        Traite la soumission du formulaire de RDV
        Crée un lead CRM + activité + envoie email de confirmation
        """
        try:
            # Récupération des données du formulaire
            name = post.get('name', '').strip()
            email = post.get('email', '').strip()
            phone = post.get('phone', '').strip()
            company = post.get('company', '').strip()
            channel_id = int(post.get('channel_id', 0))
            preferred_date = post.get('preferred_date', '')
            preferred_time = post.get('preferred_time', '')
            appointment_type = post.get('appointment_type', 'information')
            notes = post.get('notes', '').strip()

            # Validation basique
            if not name or not email or not phone:
                return request.render('lms_public_info.formation_appointment_error', {
                    'error': _("Veuillez remplir tous les champs obligatoires (nom, email, téléphone).")
                })

            # Récupérer la formation
            channel = None
            if channel_id:
                channel = request.env['slide.channel'].sudo().browse(channel_id)

            # Préparer la description
            appointment_types = {
                'information': 'Information',
                'orientation': 'Orientation',
                'assessment': 'Évaluation'
            }

            time_slots = {
                'morning': 'Matin (9h-12h)',
                'afternoon': 'Après-midi (14h-18h)',
                'evening': 'Soir (18h-20h)'
            }

            description = f"""
=== DEMANDE DE RENDEZ-VOUS ===

FORMATION :
{channel.name if channel else 'Non spécifiée'}

INFORMATIONS PROSPECT :
Nom : {name}
Email : {email}
Téléphone : {phone}
Entreprise : {company or 'Non spécifiée'}

DÉTAILS DU RDV :
Type : {appointment_types.get(appointment_type, 'Information')}
Date souhaitée : {preferred_date if preferred_date else 'Non spécifiée'}
Créneau préféré : {time_slots.get(preferred_time, 'Non spécifié')}

MESSAGE DU PROSPECT :
{notes if notes else 'Aucun message'}

---
Demande générée depuis le site web le {datetime.datetime.now().strftime('%d/%m/%Y à %H:%M')}
            """.strip()

            lead_name = f"RDV Formation - {name} - {channel.name if channel else 'Général'}"

            # Créer le lead dans une nouvelle transaction/cursor
            new_cr = request.registry.cursor()
            try:
                new_env = api.Environment(new_cr, request.env.uid, request.env.context)

                # Créer le lead
                lead_vals = {
                    'name': lead_name,
                    'phone': phone,
                    'description': description,
                    'type': 'opportunity',
                    'priority': '2',
                }

                lead = new_env['crm.lead'].sudo().with_context(
                    tracking_disable=True,
                    mail_create_nolog=True,
                    mail_create_nosubscribe=True,
                    mail_notrack=True
                ).create(lead_vals)

                # Mettre à jour l'email via SQL pour éviter la validation
                new_cr.execute("""
                    UPDATE crm_lead 
                    SET email_from = %s 
                    WHERE id = %s
                """, (email, lead.id))

                # Créer l'activité
                activity_type = new_env.ref('mail.mail_activity_data_call', raise_if_not_found=False)
                if activity_type:
                    activity_vals = {
                        'res_model_id': new_env['ir.model']._get('crm.lead').id,
                        'res_id': lead.id,
                        'activity_type_id': activity_type.id,
                        'summary': f"Rappeler {name} pour RDV formation",
                        'note': f"""Formation : {channel.name if channel else 'Non spécifiée'}<br/>
                                   Type : {appointment_types.get(appointment_type, 'Information')}<br/>
                                   Tél : {phone}<br/>
                                   Email : {email}<br/>
                                   Date souhaitée : {preferred_date or 'Non spécifiée'}<br/>
                                   Créneau : {time_slots.get(preferred_time, 'Non spécifié')}<br/>
                                   Message : {notes or 'Aucun message'}""",
                        'user_id': lead.user_id.id if lead.user_id else new_env.ref('base.user_admin').id,
                    }
                    new_env['mail.activity'].sudo().create(activity_vals)

                new_cr.commit()
                lead_id = lead.id

                _logger.info(f"Lead CRM créé dans transaction séparée : {lead_id}")

            except Exception as tx_error:
                new_cr.rollback()
                _logger.error(f"Erreur dans la transaction séparée : {tx_error}")
                raise
            finally:
                new_cr.close()

            # Envoyer l'email de confirmation
            try:
                mail_values = {
                    'subject': f'Confirmation de rendez-vous - {channel.name if channel else "Formation"}',
                    'body_html': f"""
                        <p>Bonjour {name},</p>
                        <p>Nous avons bien reçu votre demande de rendez-vous concernant notre formation <strong>{channel.name if channel else ""}</strong>.</p>
                        <p><strong>Référence :</strong> #{lead_id}</p>
                        <p>Un conseiller vous contactera dans les 48 heures ouvrées au {phone} pour convenir d'un créneau précis.</p>
                        <p>Cordialement,<br/>L'équipe FORMEVO</p>
                        """,
                    'email_to': email,
                    'email_from': request.env.company.email or 'noreply@formevo.fr',
                    'auto_delete': True,
                    'state': 'outgoing',
                }

                mail = request.env['mail.mail'].sudo().with_context(
                    default_email_from=request.env.company.email,
                    default_reply_to=request.env.company.email
                ).create(mail_values)

                mail.send()

                _logger.info(f"Email de confirmation envoyé à {email}")
            except Exception as email_error:
                _logger.warning(f"Impossible d'envoyer l'email : {email_error}")

            # Rediriger vers la page de confirmation
            return request.redirect(f"/formation/rdv/confirmation/{lead_id}")

        except Exception as e:
            _logger.error(f"Erreur lors de la soumission du formulaire RDV : {e}", exc_info=True)
            return request.render('lms_public_info.formation_appointment_error', {
                'error': _("Une erreur est survenue. Veuillez réessayer ou nous contacter directement.")
            })

    @http.route('/formation/rdv/confirmation/<int:lead_id>', type='http', auth='public', website=True)
    def formation_rdv_confirmation(self, lead_id, **kwargs):
        """Page de confirmation simplifiée"""
        try:
            lead = request.env['crm.lead'].sudo().browse(lead_id)

            if not lead.exists():
                return request.not_found()

            # Essayer de retrouver la formation depuis la description
            channel = None
            description = lead.description or ""

            if description and "FORMATION :" in description:
                # Chercher le nom de la formation dans la description
                match = re.search(r'FORMATION\s*:\s*(.+?)(?:\n|$)', description)
                if match:
                    channel_name = match.group(1).strip()
                    if channel_name and channel_name != 'Non spécifiée':
                        # Chercher la formation par nom
                        channel = request.env['slide.channel'].sudo().search(
                            [('name', 'ilike', channel_name)], limit=1
                        )

            # Extraire le nom depuis la description
            name = "Client"
            if description and "Nom :" in description:
                name_match = re.search(r'Nom\s*:\s*(.+?)(?:\n|$)', description)
                if name_match:
                    name = name_match.group(1).strip()

            return request.render('lms_public_info.formation_appointment_confirmation', {
                'lead': lead,
                'name': name,
                'email': lead.email_from,
                'channel': channel,
            })

        except Exception as e:
            _logger.error(f"Erreur lors de l'affichage de la confirmation : {e}")
            return request.redirect('/formations/catalogue')

    @http.route('/formation/notification', type='json', auth='public')
    def request_notification(self, **kwargs):
        """API pour demander une notification quand les RDV seront disponibles"""
        email = kwargs.get('email')
        action = kwargs.get('action', '')

        if not email:
            return {'success': False, 'error': 'Email requis'}

        try:
            _logger.info(f"📩 Demande de notification : {email} - Action: {action}")
            return {
                'success': True,
                'message': 'Votre demande a été enregistrée. Nous vous contacterons quand les rendez-vous seront disponibles.'
            }
        except Exception as e:
            _logger.error(f"Erreur lors de l'enregistrement de la notification : {e}")
            return {'success': False, 'error': 'Erreur serveur'}
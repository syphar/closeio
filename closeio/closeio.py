# coding=utf-8
from __future__ import (absolute_import, unicode_literals, division,
                        print_function)

import logging

import requests
from requests.adapters import HTTPAdapter
import slumber

from closeio.exceptions import CloseIOError
from closeio.utils import DummyCookieJar, paginate, handle_errors, \
    parse_response


logger = logging.getLogger(__name__)


class CloseIO(object):
    def __init__(self, api_key, max_retries=5):
        self._api_key = api_key
        self._max_retries = max_retries

    @property
    def _api(self):
        _session = requests.Session()
        _session.cookies = DummyCookieJar()
        _session.auth = (self._api_key, "")
        _session.verify = True
        _session.mount('http://', HTTPAdapter(max_retries=self._max_retries))
        _session.mount('https://', HTTPAdapter(max_retries=self._max_retries))

        return slumber.API(
            'https://app.close.io/api/v1/',
            session=_session
        )

    def __getattribute__(self, item):
        value = super(CloseIO, self).__getattribute__(item)
        if callable(value):
            return parse_response(
                handle_errors(value)
            )

        else:
            return value

    def get_lead(self, lead_id):
        return self._api.lead(lead_id).get()

    def delete_lead(self, lead_id):
        return self._api.lead(lead_id).delete()

    def get_email_templates(self):
        return paginate(
            self._api.email_template.get
        )

    def get_email_template(self, template_id):
        return self._api.email_template(template_id).get()

    def find_email_template(self, name):
        for template in self.get_email_templates():
            if template.name == name:
                return template

        raise CloseIOError(
            "EMail template with nane \"{}\" could not be found!".format(name))

    def get_opportunity_statuss(self):
        return paginate(self._api.status.opportunity.get)

    def find_opportunity_status(self, label):
        for status in self.get_opportunity_statuss():
            if status.label == label:
                return status

        raise CloseIOError(
            "Opportunity-Status with label \"{}\" "
            "could not be found!".format(label))

    def find_opportunity_status_in_organization(self, organization_id, label):
        org = self.get_organization(organization_id)

        for status in org['opportunity_statuses']:
            if status['label'] == label:
                return status

        raise CloseIOError(
            "Opportunity-Status with label \"{}\" "
            "could not be found!".format(label))

    def get_lead_statuss(self):
        return paginate(self._api.status.lead.get)

    def find_lead_status(self, label):
        for status in self.get_lead_statuss():
            if status.label == label:
                return status

        raise CloseIOError(
            "Lead-Status with label \"" + label + "\" could not be found!")

    def find_user(self, full_name):
        me = self._api.me.get()
        for membership in me['memberships']:
            org_id = membership['organization_id']

            org = self._api.organization(org_id).get()

            for user in org['memberships']:
                if user['user_full_name'] == full_name:
                    return self.get_organization_user(org_id, user['user_id'])

        raise CloseIOError(
            "User with full-name \"" + full_name + "\" could not be found!")

    def find_user_id(self, email):
        ids = set()
        email = email.strip().lower()

        me = self._api.me.get()
        for my_membership in me['memberships']:
            organization_id = my_membership['organization_id']
            org = self._api.organization(organization_id).get()
            for membership in org['memberships']:
                membership_mail = membership['user_email']
                membership_mail = membership_mail.strip().lower()

                if membership_mail == email:
                    ids.add(membership['user_id'])

        if not ids:
            raise CloseIOError("user with email {} not found".format(email))

        elif len(ids) > 1:
            raise CloseIOError(
                "multiple users with email {} found".format(email))

        else:
            return ids.pop()

    def update_lead(self, lead_id, fields):
        return self._api.lead(lead_id).put(fields)

    def create_lead(self, fields):
        return self._api.lead.post(fields)

    def create_opportunity(self, fields):
        return self._api.opportunity.post(fields)

    def update_opportunity(self, opportunity_id, fields):
        return self._api.opportunity(opportunity_id).put(fields)

    def create_task(self, lead_id, assigned_to, text, due_date=None,
                    is_complete=False):

        return self._api.task.post({
            "lead_id": lead_id,
            "assigned_to": assigned_to,
            "text": text,
            "due_date": due_date.date().isoformat() if due_date else None,
            "is_complete": is_complete
        })

    def update_task(self, task_id, fields):
        return self._api.task(task_id).put(fields)

    def get_tasks(self, lead_id=None, assigned_to=None, is_complete=None):
        args = {}

        if lead_id:
            args['lead_id'] = lead_id

        if assigned_to:
            args['assigned_to'] = assigned_to

        if is_complete is not None:
            args['is_complete'] = "true" if is_complete else "false"

        # convert to list, since we want to cache
        return paginate(
            self._api.task.get,
            **args
        )

    def create_activity_note(self, lead_id, note):
        return self._api.activity.note.post({
            'lead_id': lead_id,
            'note': note,
        })

    def create_activity_email(self, **kwargs):
        kwargs.setdefault('status', 'draft')
        self._api.activity.email.post(kwargs)

    def get_leads(self, query=None, fields=None):
        args = {}
        if query:
            args['query'] = query

        if fields:
            args['_fields'] = ','.join(fields)

        return paginate(
            self._api.lead.get,
            **args)

    def get_user(self, user_id):
        return self._api.user(user_id).get()

    def get_organization(self, organization_id):
        return self._api.organization(organization_id).get()

    def get_organization_users(self, organization_id=None):
        if not organization_id:
            organization_id = self._api.me.get()['organization_id']

        users = []

        org = self._api.organization(organization_id).get()
        for membership in org['memberships']:
            uid = membership['user_id']
            user = self._api.user(uid).get()

            user.update({
                key[5:]: value
                for key, value in membership.iteritems()
                if key.startswith('user_')
            })

            users.append(user)

        return users

    def get_organization_user(self, organization_id, user_id):
        user = self._api.user(user_id).get()

        org = self._api.organization(organization_id).get()
        for membership in org['memberships']:
            if membership['user_id'] == user_id:
                user.update({
                    key[5:]: value
                    for key, value in membership.iteritems()
                    if key.startswith('user_')
                })
                break

        else:
            raise CloseIOError(
                "User {} not found in "
                "organization {}".format(user_id, organization_id))

        return user

    def get_lead_display_name_by_id(self, lead_id):
        lead = self.get_lead(lead_id)
        if 'display_name' in lead:
            return lead['display_name']
        else:
            return None

    def get_lead_display_name(self, query):
        possible_leads = list(self.get_leads(
            query=query
        ))

        if len(possible_leads) > 0:
            if len(possible_leads) > 1:
                logger.warning(
                    "got {len} possible leads for query {query}. "
                    "Using the first one. ".format(
                        len=len(possible_leads),
                        query=query,
                    ))

            display_name = possible_leads[0].display_name
            return display_name

        return ""
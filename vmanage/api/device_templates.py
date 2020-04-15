"""Cisco vManage Device Templates API Methods.
"""

import json
import re

import dictdiffer
from vmanage.api.feature_templates import FeatureTemplates
from vmanage.api.http_methods import HttpMethods
from vmanage.data.parse_methods import ParseMethods
from vmanage.utils import list_to_dict


class DeviceTemplates(object):
    """vManage Device Templates API

    Responsible for DELETE, GET, POST, PUT methods against vManage
    Device Templates.

    """
    def __init__(self, session, host, port=443):
        """Initialize Device Templates object with session parameters.

        Args:
            session (obj): Requests Session object
            host (str): hostname or IP address of vManage
            port (int): default HTTPS 443

        """

        self.session = session
        self.host = host
        self.port = port
        self.base_url = f'https://{self.host}:{self.port}/dataservice/'
        self.feature_templates = FeatureTemplates(self.session, self.host, self.port)

    def delete_device_template(self, templateId):
        """Obtain a list of all configured device templates.

        Args:
            templateId (str): Object ID for device template

        Returns:
            result (dict): All data associated with a response.

        """

        api = f"template/device/{templateId}"
        url = self.base_url + api
        response = HttpMethods(self.session, url).request('DELETE')
        result = ParseMethods.parse_status(response)
        return result

    def get_device_templates(self):
        """Obtain a list of all configured device templates.

        Returns:
            result (dict): All data associated with a response.

        """

        api = "template/device"
        url = self.base_url + api
        response = HttpMethods(self.session, url).request('GET')
        result = ParseMethods.parse_data(response)
        return result

    #
    # Templates
    #
    def get_device_template_object(self, template_id):
        """Obtain a device template object.

        Returns:
            result (dict): All data associated with a response.

        """

        api = f"template/device/object/{template_id}"
        url = self.base_url + api
        response = HttpMethods(self.session, url).request('GET')
        if 'json' in response:
            return response['json']

        return {}

    def get_device_template_list(self, factory_default=False, name_list=None):
        """Get the list of device templates.

        Args:
            factory_default (bool): Include factory default
            name_list (list of strings): A list of template names to retreive.

        Returns:
            result (dict): All data associated with a response.
        """
        if name_list is None:
            name_list = []
        device_templates = self.get_device_templates()

        return_list = []
        feature_template_dict = self.feature_templates.get_feature_template_dict(factory_default=True,
                                                                                 key_name='templateId')

        #pylint: disable=too-many-nested-blocks
        for device in device_templates:
            # If there is a list of template name, only return the ones asked for.
            # Otherwise, return them all
            if name_list and device['templateName'] not in name_list:
                continue
            obj = self.get_device_template_object(device['templateId'])
            if obj:
                if not factory_default and obj['factoryDefault']:
                    continue
                if 'generalTemplates' in obj:
                    generalTemplates = []
                    for old_template in obj.pop('generalTemplates'):
                        new_template = {
                            'templateName': feature_template_dict[old_template['templateId']]['templateName'],
                            'templateType': old_template['templateType']
                        }
                        if 'subTemplates' in old_template:
                            subTemplates = []
                            for sub_template in old_template['subTemplates']:
                                subTemplates.append({
                                    'templateName':
                                    feature_template_dict[sub_template['templateId']]['templateName'],
                                    'templateType':
                                    sub_template['templateType']
                                })
                            new_template['subTemplates'] = subTemplates
                        generalTemplates.append(new_template)
                    obj['generalTemplates'] = generalTemplates

                    obj['templateId'] = device['templateId']
                    obj['attached_devices'] = self.get_template_attachments(device['templateId'])
                    obj['input'] = self.get_template_input(device['templateId'])
                    obj.pop('templateId')
                    return_list.append(obj)

        return return_list

    def get_device_template_dict(self, factory_default=False, key_name='templateName', remove_key=True, name_list=None):
        """Obtain a dictionary of all configured device templates.


        Args:
            factory_default (bool): Wheter to return factory default templates
            key_name (string): The name of the attribute to use as the dictionary key
            remove_key (boolean): remove the search key from the element

        Returns:
            result (dict): All data associated with a response.

        """
        if name_list is None:
            name_list = []
        device_template_list = self.get_device_template_list(factory_default=factory_default, name_list=name_list)

        return list_to_dict(device_template_list, key_name, remove_key)

    def get_template_attachments(self, template_id, key='host-name'):
        """Get the devices that a template is attached to.


        Args:
            template_id (string): Template ID
            key (string): The key of the device to put in the list (default: host-name)

        Returns:
            result (list): List of keys.

        """
        api = f"template/device/config/attached/{template_id}"
        url = self.base_url + api
        response = HttpMethods(self.session, url).request('GET')
        result = ParseMethods.parse_data(response)

        attached_devices = []
        for device in result:
            attached_devices.append(device[key])

        return attached_devices

    def get_template_input(self, template_id):
        """Get the input associated with a device attachment.


        Args:
            template_id (string): Template ID

        Returns:
            result (dict): All data associated with a response.

        """
        payload = {"deviceIds": [], "isEdited": False, "isMasterEdited": False, "templateId": template_id}
        return_dict = {
            "columns": [],
        }

        api = "template/device/config/input"
        url = self.base_url + api
        response = HttpMethods(self.session, url).request('POST', payload=json.dumps(payload))

        if response['json']:
            if 'header' in response['json'] and 'columns' in response['json']['header']:
                column_list = response['json']['header']['columns']

                regex = re.compile(r'\((?P<variable>[^(]+)\)')

                for column in column_list:
                    if column['editable']:
                        match = regex.search(column['title'])
                        if match:
                            variable = match.groups('variable')[0]
                        else:
                            variable = None

                        entry = {'title': column['title'], 'property': column['property'], 'variable': variable}
                        return_dict['columns'].append(entry)

        return return_dict

    def add_device_template(self, device_template):
        """Add a device template to Vmanage.


        Args:
            device_template (dict): Device Template

        Returns:
            result (list): Response from Vmanage

        """
        payload = {
            'templateName': device_template['templateName'],
            'templateDescription': device_template['templateDescription'],
            'deviceType': device_template['deviceType'],
            'factoryDefault': device_template['factoryDefault'],
            'configType': device_template['configType'],
            'policyId': '',
            'featureTemplateUidRange': []
        }
        #
        # File templates are much easier in that they are just a bunch of CLI
        #
        if device_template['configType'] == 'file':
            payload['templateConfiguration'] = device_template['templateConfiguration']
            api = "template/device/cli"
            url = self.base_url + api
            response = HttpMethods(self.session, url).request('POST', payload=json.dumps(payload))
        #
        # Feature based templates are just a list of templates Id that make up a devie template.  We are
        # given the name of the feature templates, but we need to translate that to the template ID
        #
        else:
            if 'generalTemplates' in device_template:
                payload['generalTemplates'] = self.generalTemplates_to_id(device_template['generalTemplates'])
            else:
                raise Exception("No generalTemplates found in device template", data=device_template)
            api = "template/device/feature"
            url = self.base_url + api
            response = HttpMethods(self.session, url).request('POST', payload=json.dumps(payload))
        return response

    def import_device_template_list(self, device_template_list, check_mode=False, update=False):
        """Add a list of feature templates to vManage.


        Args:
            check_mode (bool): Only check to see if changes would be made
            update (bool): Update the template if it exists

        Returns:
            result (list): Returns the diffs of the updates.

        """
        device_template_updates = []
        device_template_dict = self.get_device_template_dict()
        for device_template in device_template_list:
            if device_template['templateName'] in device_template_dict:
                existing_template = device_template_dict[device_template['templateName']]
                if 'generalTemplates' in device_template:
                    diff = list(
                        dictdiffer.diff(existing_template['generalTemplates'], device_template['generalTemplates']))
                elif 'templateConfiguration' in device_template:
                    diff = list(
                        dictdiffer.diff(existing_template['templateConfiguration'],
                                        device_template['templateConfiguration']))
                else:
                    raise Exception("Template {0} is of unknown type".format(device_template['templateName']))
                if len(diff):
                    device_template_updates.append({'name': device_template['templateName'], 'diff': diff})
                    if not check_mode and update:
                        if not check_mode:
                            self.add_device_template(device_template)
            else:
                if 'generalTemplates' in device_template:
                    diff = list(dictdiffer.diff({}, device_template['generalTemplates']))
                elif 'templateConfiguration' in device_template:
                    diff = list(dictdiffer.diff({}, device_template['templateConfiguration']))
                else:
                    raise Exception("Template {0} is of unknown type".format(device_template['templateName']))
                device_template_updates.append({'name': device_template['templateName'], 'diff': diff})
                if not check_mode:
                    self.add_device_template(device_template)

        return device_template_updates

    def generalTemplates_to_id(self, generalTemplates):
        converted_generalTemplates = []
        feature_templates = self.feature_templates.get_feature_template_dict(factory_default=True)
        for template in generalTemplates:
            if 'templateName' not in template:
                self.result['generalTemplates'] = generalTemplates
                self.fail_json(msg="Bad template")
            if template['templateName'] in feature_templates:
                template_item = {
                    'templateId': feature_templates[template['templateName']]['templateId'],
                    'templateType': template['templateType']
                }
                if 'subTemplates' in template:
                    subTemplates = []
                    for sub_template in template['subTemplates']:
                        if sub_template['templateName'] in feature_templates:
                            subTemplates.append({
                                'templateId':
                                feature_templates[sub_template['templateName']]['templateId'],
                                'templateType':
                                sub_template['templateType']
                            })
                        else:
                            self.fail_json(msg="There is no existing feature template named {0}".format(
                                sub_template['templateName']))
                    template_item['subTemplates'] = subTemplates

                converted_generalTemplates.append(template_item)
            else:
                self.fail_json(msg="There is no existing feature template named {0}".format(template['templateName']))

        return converted_generalTemplates
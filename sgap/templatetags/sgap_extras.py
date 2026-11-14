from django import template

from sgap.models import PermissionRequest


register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, 0)


@register.simple_tag
def status_labels():
    return PermissionRequest.Status.choices

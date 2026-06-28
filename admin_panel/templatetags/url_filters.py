from django import template

register = template.Library()

@register.filter
def without(query_dict, key):
    """
    Remove a specific key from a QueryDict and return the encoded URL string.
    """
    query_dict = query_dict.copy()  # Create a mutable copy of the QueryDict
    if key in query_dict:
        del query_dict[key]
    return query_dict.urlencode()
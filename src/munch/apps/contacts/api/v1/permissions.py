from munch.core.utils.permissions import MunchResourcePermission


class ContactListMergePermission(MunchResourcePermission):
    """ Same permissions as writing on the ContactList """
    app_name = 'contacts'
    model_name = 'contactlist'

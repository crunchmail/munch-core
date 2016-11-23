import lxml.html.clean
from lxml import etree
from lxml.html import defs
from lxml.html import xhtml_to_html
from django.template import Context
from django.template import Template
from premailer import Premailer


def css_inline_html(html, **kwargs):
    """ Contentfilter to inline CSS into HTML """
    p = Premailer(
        html=html,
        preserve_internal_links=True,
        exclude_pseudoclasses=True,
        keep_style_tags=False,
        include_star_selectors=True,
        remove_classes=False,
        strip_important=False,
        method='html',
        base_path=None,
        disable_basic_attributes=[],
        disable_validation=False,
        disable_leftover_css=True,
        align_floating_images=True,
        remove_unset_properties=True,
        capitalize_float_margin=True)
    return p.transform(pretty_print=True)


class ConditionalFriendlyCleaner(lxml.html.clean.Cleaner):
    def kill_conditional_comments(self, doc):
        # Do nothing, as we want to keep conditionals
        pass

    def kill_nonconditional_comments(self, doc):
        """ Removes all comments but IE conditionals
        """
        for el in doc.iter(etree.Comment):
            if lxml.html.clean._conditional_comment_re.match(el.text) is None:
                el.drop_tree()

    def __call__(self, doc):
        # Needed to overwrite just because of weird behaviour here:
        # https://github.com/lxml/lxml/blob/11e7f9a7d98e96ad31a1d5991b57d47472c1d143/src/lxml/html/clean.py#L308-L311
        # Let's hope it will becone unnecessary,
        # see https://github.com/lxml/lxml/pull/177

        if hasattr(doc, 'getroot'):
            # ElementTree instance, instead of an element
            doc = doc.getroot()
        # convert XHTML to HTML
        xhtml_to_html(doc)
        # Normalize a case that IE treats <image> like <img>, and that
        # can confuse either this step or later steps.
        for el in doc.iter('image'):
            el.tag = 'img'

        # BEGIN MUNCH EDIT
        # if not self.comments:
        #     # Of course, if we were going to kill comments anyway, we don't
        #     # need to worry about this
        #     self.kill_conditional_comments(doc)
        # END MUNCH EDIT

        kill_tags = set(self.kill_tags or ())
        remove_tags = set(self.remove_tags or ())
        allow_tags = set(self.allow_tags or ())

        if self.scripts:
            kill_tags.add('script')
        if self.safe_attrs_only:
            safe_attrs = set(self.safe_attrs)
            for el in doc.iter(etree.Element):
                attrib = el.attrib
                for aname in attrib.keys():
                    if aname not in safe_attrs:
                        del attrib[aname]
        if self.javascript:
            if not (self.safe_attrs_only and
                    self.safe_attrs == defs.safe_attrs):
                # safe_attrs handles events attributes itself
                for el in doc.iter(etree.Element):
                    attrib = el.attrib
                    for aname in attrib.keys():
                        if aname.startswith('on'):
                            del attrib[aname]
            doc.rewrite_links(self._remove_javascript_link,
                              resolve_base_href=False)
            if not self.style:
                # If we're deleting style then we don't have to remove JS links
                # from styles, otherwise...
                for el in lxml.html.clean._find_styled_elements(doc):
                    old = el.get('style')
                    new = lxml.html.clean._css_javascript_re.sub('', old)
                    new = lxml.html.clean._css_import_re.sub('', new)
                    if self._has_sneaky_javascript(new):
                        # Something tricky is going on...
                        del el.attrib['style']
                    elif new != old:
                        el.set('style', new)
                for el in list(doc.iter('style')):
                    if el.get('type', '').lower().strip() == 'text/javascript':
                        el.drop_tree()
                        continue
                    old = el.text or ''
                    new = lxml.html.clean._css_javascript_re.sub('', old)
                    # The imported CSS can do anything; we just can't allow:
                    new = lxml.html.clean._css_import_re.sub('', old)
                    if self._has_sneaky_javascript(new):
                        # Something tricky is going on...
                        el.text = '/* deleted */'
                    elif new != old:
                        el.text = new
        # START MUNCH MODIFICATION
        if self.comments:
            # kill_tags.add(etree.Comment)
            self.kill_nonconditional_comments(doc)
        # END MUNCH MODIFICATION
        if self.processing_instructions:
            kill_tags.add(etree.ProcessingInstruction)
        if self.style:
            kill_tags.add('style')
            etree.strip_attributes(doc, 'style')
        if self.links:
            kill_tags.add('link')
        elif self.style or self.javascript:
            # We must get rid of included stylesheets if Javascript is not
            # allowed, as you can put Javascript in them
            for el in list(doc.iter('link')):
                if 'stylesheet' in el.get('rel', '').lower():
                    # Note this kills alternate stylesheets as well
                    if not self.allow_element(el):
                        el.drop_tree()
        if self.meta:
            kill_tags.add('meta')
        if self.page_structure:
            remove_tags.update(('head', 'html', 'title'))
        if self.embedded:
            # FIXME: is <layer> really embedded?
            # We should get rid of any <param> tags not inside <applet>;
            # These are not really valid anyway.
            for el in list(doc.iter('param')):
                parent = el.getparent()
                while parent is not None and parent.tag not in (
                        'applet', 'object'):
                    parent = parent.getparent()
                if parent is None:
                    el.drop_tree()
            kill_tags.update(('applet',))
            # The alternate contents that are in an iframe are a good fallback:
            remove_tags.update(('iframe', 'embed', 'layer', 'object', 'param'))
        if self.frames:
            # FIXME: ideally we should look at the frame links, but
            # generally frames don't mix properly with an HTML
            # fragment anyway.
            kill_tags.update(defs.frame_tags)
        if self.forms:
            remove_tags.add('form')
            kill_tags.update(('button', 'input', 'select', 'textarea'))
        if self.annoying_tags:
            remove_tags.update(('blink', 'marquee'))

        _remove = []
        _kill = []
        for el in doc.iter():
            if el.tag in kill_tags:
                if self.allow_element(el):
                    continue
                _kill.append(el)
            elif el.tag in remove_tags:
                if self.allow_element(el):
                    continue
                _remove.append(el)

        if _remove and _remove[0] == doc:
            # We have to drop the parent-most tag, which we can't
            # do.  Instead we'll rewrite it:
            el = _remove.pop(0)
            el.tag = 'div'
            el.attrib.clear()
        elif _kill and _kill[0] == doc:
            # We have to drop the parent-most element, which we can't
            # do.  Instead we'll clear it:
            el = _kill.pop(0)
            if el.tag != 'html':
                el.tag = 'div'
            el.clear()

        _kill.reverse()  # start with innermost tags
        for el in _kill:
            el.drop_tree()
        for el in _remove:
            el.drop_tag()

        if self.remove_unknown_tags:
            if allow_tags:
                raise ValueError((
                    "It does not make sense to pass in both "
                    "allow_tags and remove_unknown_tags"))
            allow_tags = set(defs.tags)
        if allow_tags:
            bad = []
            for el in doc.iter():
                if el.tag not in allow_tags:
                    bad.append(el)
            if bad:
                if bad[0] is doc:
                    el = bad.pop(0)
                    el.tag = 'div'
                    el.attrib.clear()
                for el in bad:
                    el.drop_tag()

        if self.add_nofollow:
            for el in lxml.html.clean._find_external_links(doc):
                if not self.allow_follow(el):
                    rel = el.get('rel')
                    if rel:
                        if (
                                'nofollow' in rel and ' nofollow ' in (
                                    ' %s ' % rel)):
                            continue
                        rel = '%s nofollow' % rel
                    else:
                        rel = 'nofollow'
                    el.set('rel', rel)


# Waiting for https://github.com/lxml/lxml/pull/178 integration for comment
# tbody removal is linked to
# https://blog.mailchimp.com/spam-filters-dont-like-microsoft/

_allowed_tags = (
    defs.tags | frozenset([etree.Comment])) \
    - frozenset(['tbody', 'thead', 'tfoot'])
cleaner = ConditionalFriendlyCleaner(
    scripts=True,
    javascript=True,
    embedded=True,
    safe_attrs_only=False,
    links=True,
    page_structure=False,  # avoid wrapping everything in a div...
    comments=True,  # Non-conditionals only
    allow_tags=_allowed_tags,
    remove_unknown_tags=False)


def clean_html(html, **kwargs):
    """ Contentfilter to remove js & others from HTML """
    return cleaner.clean_html(html)


def apply_mailmerge(html, mail_properties={}, **kwargs):
    tpl = Template(html)
    return tpl.render(Context(mail_properties))

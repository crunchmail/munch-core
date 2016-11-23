import functools

import lxml.etree
from lxml.cssselect import CSSSelector
from django.urls import reverse

from munch.core.utils.regexp import mkd_footnote_url_re

from .utils import WebKey

body_selector = CSSSelector('body')
links_selector = CSSSelector('a')


def mk_tracking_url(app_url, mail_identifier):
    """ Builds the tracking image at that url

    :type mail: campaigns.Mail
    :returns: the absolute url of the tracking image
    """
    return '{}/{}'.format(
        app_url, reverse(
            'tracking-open',
            kwargs={'identifier': mail_identifier}).strip('/'))


def add_tracking_image(
        html, app_url=None, track_open=False, mail_identifier=None, **kwargs):
    """ Content filter to add tracking Pixel

    Appends a <img> tag to the HTML, pointing to a tracking with id in
    querystring
    """
    if track_open and app_url and mail_identifier:
        # use the root tree to preserve doctype
        doc = lxml.etree.HTML(html).getroottree()
        img = lxml.etree.fromstring(
            '<img src="{}" alt="" height="1" width="1" border="0" />'.format(
                mk_tracking_url(app_url, mail_identifier)))

        body = body_selector(doc)

        if len(body) > 0:
            body[0].append(img)
        else:
            doc.append(img)

        with_image = lxml.html.tostring(doc).decode()
        return with_image
    return html


class LinksRewriter:
    @staticmethod
    def rewrite(mail_identifier, app_url, links_map, url):
        """ Makes a redirection url used for email links
        """
        # invert the message links_map so we can look by URL
        if links_map:
            links_map = {v: k for k, v in links_map.items()}
        if url in links_map:
            return '{}/{}'.format(
                app_url,
                reverse('tracking-redirect',
                        kwargs={
                            'identifier': mail_identifier,
                            'link_identifier': links_map[url]}).strip('/'))
        return url

    @staticmethod
    def should_rewrite(link, unsubscribe_url):
        """ Just a place to store a blacklist of links not to be rewritten

        FIXME: can be removed I think
        """
        if link == unsubscribe_url:
            return False
        return True


class HTMLLinksRewriter(LinksRewriter):
    @classmethod
    def _rewrite_html_links(
            cls, html, track_clicks, mail_identifier,
            unsubscribe_url, app_url, links_map, rewrite_func):
        """ Generic Content filter to rewrite links

        :param rewrite_func: f(Mail, original_url) -> rewritten_url
        """
        if track_clicks and \
                not mail_identifier.startswith('test'):
            # use the root tree to preserve doctype
            doc = lxml.etree.HTML(html).getroottree()

            for link in links_selector(doc):
                original_url = link.get('href') or ''
                original_url = original_url.strip()

                if (
                        original_url.startswith('http') and cls.should_rewrite(
                            original_url, unsubscribe_url)):
                    link.set('href', rewrite_func(
                        mail_identifier, app_url,
                        links_map, original_url))

            return lxml.html.tostring(doc).decode()
        return html


class HTMLEMailLinksRewriter(HTMLLinksRewriter):
    def __call__(
            self, html, app_url=None, track_clicks=False,
            mail_identifier=None, unsubscribe_url=None,
            links_map={}, **kwargs):
        """ Content filter to add tracked links for mails """
        return self._rewrite_html_links(
            html, track_clicks, mail_identifier,
            unsubscribe_url, app_url, links_map, self.rewrite)


rewrite_html_links = HTMLEMailLinksRewriter()


class PlaintextLinksRewriter(LinksRewriter):
    def __call__(
            self, plaintext, app_url=None, unsubscribe_url=None,
            mail_identifier=None, links_map={}, **kwargs):
        rewriter = functools.partial(
            self._rewrite_link,
            app_url=app_url,
            links_map=links_map,
            unsubscribe_url=unsubscribe_url,
            mail_identifier=mail_identifier)
        return mkd_footnote_url_re.sub(rewriter, plaintext)

    @classmethod
    def _rewrite_link(
            cls, m, app_url, links_map, unsubscribe_url, mail_identifier):
        url = m.group('url')
        footnote_mark = m.group('fnmark')
        if cls.should_rewrite(url, unsubscribe_url) and \
                not mail_identifier.startswith('test'):
            return '{} {}'.format(footnote_mark, cls.rewrite(
                mail_identifier, app_url, links_map, url))
        return m.group(0)  # as-is


rewrite_plaintext_links = PlaintextLinksRewriter()


class WebVersionLinksRewriter(HTMLLinksRewriter):
    def __call__(
            self, html, app_url=None, track_clicks=False,
            unsubscribe_url=None, mail_identifier=None,
            links_map={}, **kwargs):
        return self._rewrite_html_links(
            html, track_clicks, mail_identifier, unsubscribe_url,
            app_url, links_map, self.rewrite)

    @staticmethod
    def rewrite(mail_identifier, app_url, links_map, url):
        """Makes a redirection url used for links in web version

        It's based on web key.
        """
        webkey = WebKey.from_instance(mail_identifier)
        # invert the message links_map so we can look by URL
        links_map = {v: k for k, v in links_map.items()}

        if url in links_map:
            return '{}/{}'.format(
                app_url,
                reverse('web-tracking-redirect',
                        kwargs={
                            'web_key': webkey.token,
                            'link_identifier': links_map[url]}).strip('/'))
        return url


web_rewrite_html_links = WebVersionLinksRewriter()

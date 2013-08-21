# -*- coding: utf-8 -*-
"""
Created on 18 juil. 2013
"""
from __future__ import unicode_literals
import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import sys
import os
from django.template import loader
from django.template.context import Context
import shutil
from pprint import pprint
import codecs
logger = logging.getLogger(__name__)


from optparse import make_option

class Command(BaseCommand):
    args = '<destination>'
    help = 'generate a ready-to-use nginx config for the current project'
    option_list = BaseCommand.option_list + (
        make_option('--socket',
            action='store',
            dest='socket',
            default="/var/run/django/{fqdn}.sock",
            help='the socket to use to contact gunicorn. can add {fqdn} to insert FQDN. default to /var/run/django/{fqdn}.sock'),
        make_option('--workon_home',
            action='store',
            dest='workon_home',
            default=None,
            help='the directory of the workon home (where is located all virtualenv)'),

        make_option('--setting',
            action='append',
            dest='extra_settings',
            default=[],
            help='overide a value defaulted by the settings value. ie: --setting=FQDN=myproj.exemple.com'),
         make_option('--no-buildout',
            action='store_true',
            dest='buildout',
            default=False,
            help="don't set path as if project was in a buildout cookpot"),

        )

    taken_from_settings = (
                           # (settings name, default value),
                           ("ADMINISTRATOR_IP", "127.0.0.1"),
                           ("FQDN"),
                           ("SITE_NAME"),
                           ("DOMAIN_NAME"),
                           ("ADMINISTRATOR_IP"),
                           ("DJANGO_ROOT"),
                           ("SECURE_PREFIX"),
                           ("STATIC_ROOT"),
                           ("MEDIA_ROOT"),
                           )

    template_files = (
                      "sub.domain.ext",
                      "sub.domain.ext.d/dynamic.conf",
                      "sub.domain.ext.d/static.conf",
                      "sub.domain.ext.d/gunicorn.conf",
                      "sub.domain.ext.d/extra/di.maintenance.conf",
                      "sub.domain.ext.d/switch_maintenance.sh",
                      "django_sub.domain.ext"

                      )

    def handle(self, *args, **options):
        if len(args) > 0:
            dest = args[0]
        else:
            dest = "nginx_conf"
        socket = options["socket"]
        buildout = not options["buildout"]
        workon_home = options["workon_home"]
        if workon_home is None:
            try:
                workon_home = os.environ["WORKON_HOME"]
                self.stderr.write("guesing workon home with environ : %s" % workon_home)
            except:
                raise CommandError("impossible to get workon_home. pleas set an environement or with --workon_home")

        # constructing overriden settings
        extra_settings = {}
        for opt_settings in options["extra_settings"]:
            splited = opt_settings.split("=")
            extra_settings[splited[0]] = "=".join(splited[1:])

        context = {"buildout": buildout,
                   "WORKON_HOME": workon_home}

        errors = False
        for res in self.taken_from_settings:
            if isinstance(res, (tuple, list)):
                if extra_settings.has_key(res[0]):
                    context[res[0]] = extra_settings[res[0]]
                    continue
                try:
                    settingsname, default = res
                    context[settingsname] = getattr(settings, settingsname, default)
                except ValueError:
                    # dont have default value
                    try:
                        context[settingsname] = getattr(settings, settingsname)
                    except AttributeError:
                        errors = True
                        self.stderr.write('setting {0} absent from settings. try to ovenride it with --setting={0}=FOO'.format(settingsname))

            else:

                try:
                    settingsname = res
                    context[settingsname] = getattr(settings, settingsname)
                except AttributeError:
                    errors = True
                    self.stderr.write('setting {0} absent from settings. try to ovenride it with --setting={0}=FOO'.format(settingsname))

        if errors:
            raise CommandError("dont continu because of previous settings missing")

        socket = socket.format(fqdn=context["FQDN"])

        if socket.startswith("/"):
            context["socket"] = "unix:%s" % socket
        else:
            context["socket"] = socket

        self.stdout.write("context variable used :")
        pprint(context)

        tmpl_context = Context(context)

        #  create arbo
        try:
            os.chdir(dest)
        except:
            os.makedirs(dest)
            os.chdir(dest)

        try:
            os.mkdir("%s.d" % context["FQDN"])
        except OSError:
            pass
        try:
            os.mkdir(os.path.join("%s.d" % context["FQDN"], "extra"))
        except OSError:
            pass

        for template_file in self.template_files:
            with codecs.open(template_file.replace("sub.domain.ext", context["FQDN"]), "w", encoding="utf-8") as output:
                template = loader.get_template("django_nginx/%s" % template_file)
                print("writing %s" % os.path.join(dest, output.name))
                output.write(template.render(tmpl_context))

        self.stderr.write("done")


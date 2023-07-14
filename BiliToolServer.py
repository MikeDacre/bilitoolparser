#!/usr/bin/env python3
"""A simple web server to parse GET requests and scrape emr.bilitool.org to create a template.

Required GET args = age, ga, and one of tbili (serum) or tcb
Recommended args = tbili, dbili, alb

e.g. http://localhost:8080/?age=46&ga=38w5d&tcb=6.3&tbili=6.7&dbili=2.7&alb=3.4

"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json, time, requests, traceback
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import pandas as pd
# Requires lxml too

# If serving publically, use a reverse proxy
hostName = "localhost"
serverPort = 8080


class ParseBili(BaseHTTPRequestHandler):
    """Web server GET request handler"""

    def __init__(self, *args, **kwargs):
        self.expected = ["age", "ga"]

        self.neuro = '\n'.join(
            ["- GA < 38wk",
             "- ETCOc > 1.7 ppm",
             "- Hemolytic risk: Isoimmune disease, G6PD, etc",
             "- Albumin < 3 g/dL",
             "- Significant clinical instability in last 24 hours", ""
            ]
        )
        self.bili_tcb  = 'TcB: {tcb}'
        self.bili_tsb  = 'TsB: {tsb}'
        self.bili_both = 'TcB: {tcb}\nTsB {tsb}'
        self.template_text = '\n'.join(
            [
             '{bili_info}',
             '',
             'Threshold for checking TsB per 2022 AAP hyperbilirubinemia recommendations: {tsbchk}', 'TsB recommended: {tsbrec}',
             '{tstxt}',
             'TsB phototherapy threshold per 2022 AAP hyperbilirubinemia recommendations: {photoval}', 'Phototherapy recommended: {photorec}'
            ]
        )
        self.outtext_hr = '\n'.join(
            ['Submitted values:', '{submission}', '',
             "Your patient has been identified as having neuro risk factors based on: {hrs}.",
             "", "",
             'For reference, neurotoxicity risk factors per AAP are:',
             '{neuro}',
             'To view the bilitool.org result click <a href={hrurl} targe="_blank">here</a>',
             "",
             'Template text:',
             '--------------',
             "",
             '{template}'
            ]
        )
        self.outtext_other = '\n'.join(
            ['Submitted values:', '{submission}', '',
            "Your patient has <strong>not</strong> been identified as high risk based on albumin or gestational age. ",
            "",
            "If they have hemolytic disease or have been significantly unstable in the last 24 hours, use",
            "the high risk template, otherwise use the low risk template.",
            "",
            "Neuro Risk Factors:",
            "{neuro}",
            "To view the bilitool.org report for neuro risk factors <strong>present</strong> click <a href={hrurl} target='_blank'>here</a>",
            "To view the bilitool.org report for neuro risk factors <strong>absent</strong> click <a href={lrurl} target='_blank'>here</a>",
            "",
            "High risk template:",
            '-------------------',
            "",
            "{hrtemp}",
            "",
            "Low risk template:",
            '------------------',
            "",
            "{lrtemp}"
            ]
        )

        self.myheaders={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}
        super(ParseBili, self).__init__(*args, **kwargs)

    def do_GET(self):
        """Take GET args, send to bilitool via parse_bili and display template text.

        Required args: age, ga, and one or both of tcb/tbili
        Recommended args: alb, dbili
        """
        request = urlparse(self.path)
        # Only accept http and https schemas
        #  if not request.scheme in ['http', 'https']:
            #  self.send_error(400, 'Invalid request scheme {}.\n'.format(request.scheme))
            #  self.send_response(400)
            #  return
        # Parse Query
        args = {}
        try:
            for part in request.query.split('&'):
                if '=' in part:
                    q = part.split('=')
                    args[q[0]] = q[1]
        except Exception as e:
            print('\n'.join(traceback.format_exception(e)))
            self.send_error(500, 'Unable to parse url. Error "{}". Please contact the developer'.format(str(e)))
            return
        # Check that mandatory elements are present
        failed = []
        for i in self.expected:
            if not i in args:
                failed.append(i)
        if not len(failed) == 0:
            print("400 error. Invalid query. Query {}".format(request))
            self.send_error(400, "Invalid query string. Parts: {}, Missing: {}".format(args, failed))
            return
        if not 'tcb' in args and not 'tbili' in args:
            print("400 error. Neither tcb nor tbili. Query {}".format(request))
            self.send_error(400, "Invalid query string. Must include either tcb or tbili. Parts: {}".format(args))
            return
        # Run the main function
        try:
            output = self.parse_bili(args)
            output = '<br>\n'.join(output.split('\n')).strip()
            output = '<p style="line-height: 20px; margin-bottom: 10px;">{}</p>'.format(output)
        except Exception as e:
            print('\n'.join(traceback.format_exception(e)))
            self.send_error(500, 'The parse_bili function failed with error "{}". Please contact the developer'.format(str(e)))
            return
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(output.encode('utf8'))
        return

    def parse_bili(self, args):
        age = int(args['age'])
        ga = args['ga']
        gaw = self.split_ga(ga)
        if gaw < 35:
            self.send_error(400, "Tool cannot be used at less than 35 weeks gestation")
        tcb = float(args['tcb']) if 'tcb' in args else None
        alb = float(args['alb']) if 'alb' in args else None
        tbili = float(args['tbili']) if 'tbili' in args and len(args['tbili']) > 0 else '***'
        dbili = float(args['dbili']) if 'dbili' in args and len(args['dbili']) > 0 else '***'
        tsb = False if tbili == '***' else True
        # Prefer serum bili
        if tsb and tcb:
            bili_info = self.bili_both.format(tcb=tcb, tsb=tbili)
            bili = float(tbili)
        elif tsb:
            bili_info = self.bili_tsb.format(tsb=tbili)
            bili = float(tbili)
        elif tcb:
            bili_info = self.bili_tcb.format(tcb=tcb)
            bili = tcb
        else:
            raise Exception('Need either tcb or tbili')
        tstxt = "\nTotal Serum Bilirubin: {}\nDirect Bilirubin: {}\n".format(tbili, dbili)

        if gaw < 38 and alb and alb < 3:
            hrsk = True
            hrs = "gestational age < 38w and infant has an albumin < 3 g/dL"
        elif gaw < 38:
            hrsk = True
            hrs = "gestational age is < 38w"
        elif alb and alb < 3:
            hrsk = True
            hrs = "Patient has an albumin < 3 g/dL"
        else:
            hrsk = False

        # Get high risk output
        hrurl = "https://emr.bilitool.org/results.php?ageHours={}&totalBilirubin={}&bilirubinUnits=US&gestationalWeeks={}&neuroRiskFactors=Yes".format(age, bili, gaw)
        hrpage = requests.get(hrurl, headers=self.myheaders)
        hrhtable = BeautifulSoup(hrpage.content, "html.parser").findAll(attrs={'class': 'table'})[1]
        hr = pd.read_html(hrhtable.prettify())[0]
        hrd = {
            'tsb_rec' : hr['Recommendations.1'][2],
            'tsb_val' : hr['Copy to Clipboard'][2],
            'pho_rec' : hr['Recommendations.1'][4],
            'pho_val' : hr['Copy to Clipboard'][4],
            'esc_rec' : hr['Recommendations.1'][5],
            'esc_val' : hr['Copy to Clipboard'][5],
            'exc_rec' : hr['Recommendations.1'][6],
            'exc_val' : hr['Copy to Clipboard'][6]
        }
        hrtemp = self.template_text.format(bili_info=bili_info, tsbchk=hrd['tsb_val'], tsbrec=hrd['tsb_rec'], bili=bili, tstxt=tstxt, photoval=hrd['pho_val'], photorec=hrd['pho_rec'])
        if hrsk:
            return self.outtext_hr.format(hrs=hrs, submission=args, neuro=self.neuro, hrurl=hrurl, template=hrtemp)

        # Do low risk if can't predict high risk
        lrurl = "https://emr.bilitool.org/results.php?ageHours={}&totalBilirubin={}&bilirubinUnits=US&gestationalWeeks={}&neuroRiskFactors=No".format(age, bili, gaw)
        lrpage = requests.get(lrurl, headers=self.myheaders)
        lrhtable = BeautifulSoup(lrpage.content, "html.parser").findAll(attrs={'class': 'table'})[1]
        lr = pd.read_html(lrhtable.prettify())[0]
        lrd = {
            'tsb_rec' : lr['Recommendations.1'][2],
            'tsb_val' : lr['Copy to Clipboard'][2],
            'pho_rec' : lr['Recommendations.1'][4],
            'pho_val' : lr['Copy to Clipboard'][4],
            'esc_rec' : lr['Recommendations.1'][5],
            'esc_val' : lr['Copy to Clipboard'][5],
            'exc_rec' : lr['Recommendations.1'][6],
            'exc_val' : lr['Copy to Clipboard'][6]
        }
        if not tsb and bili < float(lrd['tsb_val'].split(' ')[0]):
            tstxt = ''
        lrtemp = self.template_text.format(bili_info=bili_info, tsbchk=lrd['tsb_val'], tsbrec=lrd['tsb_rec'], tstxt=tstxt, photoval=lrd['pho_val'], photorec=lrd['pho_rec'])
        return self.outtext_other.format(neuro=self.neuro, submission=args, hrurl=hrurl, lrurl=lrurl, hrtemp=hrtemp, lrtemp=lrtemp)

    def split_ga(self, ga):
        """Split standard gestational age strings

        Glossary: WW = weeks, e.g. 38, D = day of week, e.g. 3

        self.ga -- A string or int in the form WWwDd, WW, WW'd
        """
        if isinstance(ga, str):
            if 'w' in ga:
                gas = ga.split('w')
            elif ' ' in ga:
                gas = ga.split(' ')
            elif "'" in ga:
                gas = ga.split("'")
            else:
                gas = [ga]
            if len(gas) == 1:
                gaw = int(gas[0])
            elif len(gas) == 2:
                gaw = int(gas[0])
                gad = int(gas[1].strip('d'))
                # Round up the week as long as we don't go over the 38 week threshold
                if gad > 3 and gaw != 37:
                    gaw += 1
            else:
                self.send_error(400, "Weeks must be in the for WW, WWwD, or WW'd. Was {}".format(gas))
        else:
            gaw = int(ga)
        return gaw

if __name__ == "__main__":
    webServer = HTTPServer((hostName, serverPort), ParseBili)
    print("Server started http://%s:%s" % (hostName, serverPort))

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass

    webServer.server_close()
    print("Server stopped.")

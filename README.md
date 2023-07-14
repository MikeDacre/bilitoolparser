# emr.bilitool.org parser

Web app to send structured data to emr.bilitool.org and return an EPIC compatible template

Required GET args = age, ga, and one of tbili (serum) or tcb
Recommended args = tbili, dbili, alb

e.g. http://localhost:8080/?age=46&ga=38w5d&tcb=6.3&tbili=6.7&dbili=2.7&alb=3.4


To install, run on a machine with python3 and the following modules:
- bs4
- pandas
- lxml

If serving publically, be sure to put behind an nginx reverse proxy with an ssl
cert.

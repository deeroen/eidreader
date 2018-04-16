# Copyright 2018 Rumma & Ko Ltd
# License: BSD (see file COPYING for details)
"""
Read the Belgian eID card from reader and display the data to
stdout or post it to a web server.

Details see http://eidreader.lino-framework.org/usage.html
"""

import logging
logger = logging.getLogger(__name__)

import os
import argparse
import requests
# from eidreader import eid2dict
from eidreader import SETUP_INFO
import base64
import platform
from PyKCS11 import PyKCS11, CKA_CLASS, CKO_DATA, CKA_LABEL, CKA_VALUE


SCHEMESEP = '://'

images = set("""
PHOTO_FILE
""".split())
# ignored:
# DATA_FILE
# CERT_RN_FILE
# SIGN_DATA_FILE
# SIGN_ADDRESS_FILE
# ADDRESS_FILE

fields = set("""
carddata_os_number
carddata_os_version
carddata_soft_mask_number
carddata_soft_mask_version
carddata_appl_version
carddata_glob_os_version
carddata_appl_int_version
carddata_pkcs1_support
carddata_key_exchange_version
carddata_appl_lifecycle
card_number
validity_begin_date
validity_end_date
issuing_municipality
national_number
surname
firstnames
first_letter_of_third_given_name
nationality
location_of_birth
date_of_birth
gender
nobility
document_type
special_status
duplicata
special_organization
member_of_family
date_and_country_of_protection
address_street_and_number
address_zip
address_municipality
""".split())

# the following fields caused encoding problems, so we ignore them for
# now:
# carddata_serialnumber
# carddata_comp_code
# chip_number
# photo_hash


def eid2dict():
    if 'PYKCS11LIB' not in os.environ:
        if platform.system().lower() == 'linux':
            os.environ['PYKCS11LIB'] = 'libbeidpkcs11.so.0'
        else:
            os.environ['PYKCS11LIB'] = 'beidpkcs11.dll'

    pkcs11 = PyKCS11.PyKCS11Lib()
    pkcs11.load()

    slots = pkcs11.getSlotList()
    
    data = dict(eidreader_version=SETUP_INFO['version'], success=False)
    
    # if len(slots) == 0:
    #     quit("No slot available")

    # fields = [
    #     'surname',
    #     'firstnames',
    #     'other_names',
    #     'gender',
    #     'nationality',
    #     'document_type',
    #     'address_municipality',
    #     'address_zip',
    #     'date_of_birth',
    #     'national_id',
    #     'card_id',
    #     'valid_until',
    #     'location_of_birth',
    #     'date_issued',
    #     'address_street_and_number',
    #     'date_and_country_of_protection']

    # images = ['PHOTO_FILE', 'SIGN_DATA_FILE']

    for slot in slots:
        # card_data = {}
        try:
            # sess = eid.open_session(slot)
            sess = pkcs11.openSession(slot)
        except PyKCS11.PyKCS11Error:
            continue
            # data.update(error=str(e))
            # quit("Error: {}".format(e))
            
        # print(dir(sess))
        objs = sess.findObjects([(CKA_CLASS, CKO_DATA)])
        # print(len(objs))
        # print(type(objs[0]), dir( objs[0]), objs[0].to_dict())
        for o in objs:
            label = sess.getAttributeValue(o, [CKA_LABEL])[0]
            value = sess.getAttributeValue(o, [CKA_VALUE])
            if len(value) == 1:
                # value = ''.join(chr(i) for i in value[0])
                value = bytes(value[0])
                if label in fields:
                    # value = value.decode('utf-8')
                    try:
                        value = value.decode('utf-8')
                    except UnicodeDecodeError:
                        print("20180414 {} : {!r}".format(label, value))
                    data[label] = value
                elif label in images:
                    value = base64.b64encode(value)
                    data[label] = value
            # print("{}: {}".format(label, value))
            # d = o.to_dict()
            # print(o['CKA_LABEL'])
        #     d['TLV'] = ''.join(chr(i) for i in d['CKA_VALUE']) if 'CKA_VALUE' in d else ''
        #     print("%(CKA_CLASS)s %(CKA_LABEL)s %(TLV)r" % d )
        # for o in objs:
        #     print(o, dir( o ))
        # data.update(card_data=card_data)
        data.update(success=True)
        data.update(eidreader_country="BE")
        # del data['error']
            
            
    return data




def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", default=None, nargs='?')
    args = parser.parse_args()
    url = args.url
    
    if url:
        lst = url.split(SCHEMESEP, 2)
        if len(lst) == 3:
            url = lst[1] + SCHEMESEP + lst[2]
        elif len(lst) == 2:
            pass
            # url = lst[1]
        else:
            quit("Invalid URL {}".format(url))

        data = eid2dict()
        print("POST to {}: {}".format(url, data))
        r = requests.post(url, data=data)
        print("POST returned {}".format(r))
    else:
        print(eid2dict())

if __name__ == '__main__':    
    main()
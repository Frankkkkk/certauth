import logging
import os
from OpenSSL import crypto
from OpenSSL.SSL import FILETYPE_PEM
import random
from argparse import ArgumentParser


#=================================================================
# Duration of 100 years
CERT_DURATION = 100 * 365 * 24 * 60 * 60

CERTS_DIR = './pywb-certs/'

CERT_NAME = 'pywb https proxy replay CA'

CERT_CA_FILE = './pywb-ca.pem'


#=================================================================
class CertificateAuthority(object):
    """
    Utility class for signing individual certificate
    with a root cert.

    Static generate_ca_root() method for creating the root cert

    All certs saved on filesystem. Individual certs are stored
    in specified certs_dir and reused if previously created.
    """

    def __init__(self, ca_file, certs_dir):
        if not ca_file:
            ca_file = CERT_CA_FILE

        if not certs_dir:
            certs_dir = CERTS_DIR

        self.ca_file = ca_file
        self.certs_dir = certs_dir

        # read previously created root cert
        self.cert, self.key = self.read_pem(ca_file)

        if not os.path.exists(certs_dir):
            os.mkdir(certs_dir)

    def get_cert_for_host(self, host, overwrite=False):
        host_filename = os.path.sep.join([self.certs_dir, '%s.pem' % host])

        if not overwrite and os.path.exists(host_filename):
            return False, host_filename

        self.generate_host_cert(host, self.cert, self.key, host_filename)
        return True, host_filename

    @staticmethod
    def _make_cert(certname):
        cert = crypto.X509()
        cert.set_version(3)
        cert.set_serial_number(random.randint(0, 2 ** 64 - 1))
        cert.get_subject().CN = certname

        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(CERT_DURATION)
        return cert

    @staticmethod
    def generate_ca_root(ca_file, certname=None, overwrite=False):
        if not certname:
            certname = CERT_NAME

        if not ca_file:
            ca_file = CERT_CA_FILE

        if not overwrite and os.path.exists(ca_file):
            cert, key = CertificateAuthority.read_pem(ca_file)
            return False, cert, key

        # Generate key
        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, 2048)

        # Generate cert
        cert = CertificateAuthority._make_cert(certname)

        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(key)
        cert.add_extensions([
            crypto.X509Extension(b"basicConstraints",
                                 True,
                                 b"CA:TRUE, pathlen:0"),

            crypto.X509Extension(b"keyUsage",
                                 True,
                                 b"keyCertSign, cRLSign"),

            crypto.X509Extension(b"subjectKeyIdentifier",
                                 False,
                                 b"hash",
                                 subject=cert),
            ])
        cert.sign(key, "sha1")

        # Write cert + key
        CertificateAuthority.write_pem(ca_file, cert, key)
        return True, cert, key

    @staticmethod
    def generate_host_cert(host, root_cert, root_key, host_filename):
        # Generate key
        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, 2048)

        # Generate CSR
        req = crypto.X509Req()
        req.get_subject().CN = host
        req.set_pubkey(key)
        req.sign(key, 'sha1')

        # Generate Cert
        cert = CertificateAuthority._make_cert(host)

        cert.set_issuer(root_cert.get_subject())
        cert.set_pubkey(req.get_pubkey())
        cert.sign(root_key, 'sha1')

        # Write cert + key
        CertificateAuthority.write_pem(host_filename, cert, key)
        return cert, key

    @staticmethod
    def write_pem(filename, cert, key):
        with open(filename, 'wb+') as f:
            f.write(crypto.dump_privatekey(FILETYPE_PEM, key))

            f.write(crypto.dump_certificate(FILETYPE_PEM, cert))

    @staticmethod
    def read_pem(filename):
        with open(filename, 'r') as f:
            cert = crypto.load_certificate(FILETYPE_PEM, f.read())
            f.seek(0)
            key = crypto.load_privatekey(FILETYPE_PEM, f.read())

        return cert, key


#=================================================================
def main():
    parser = ArgumentParser(description='Cert Auth Cert Maker')

    parser.add_argument('output_file', help='path to certificate file')

    parser.add_argument('-r', '--use-root',
                        help='use specified root cert to create signed cert')

    parser.add_argument('-n',  '--name', action='store', default=CERT_NAME,
                        help='name for root certificate')

    parser.add_argument('-d', '--certs-dir', default=CERTS_DIR)

    parser.add_argument('-f', '--force', action='store_true')

    result = parser.parse_args()

    overwrite = result.force

    # Create a new signed certificate using specified root
    if result.use_root:
        certs_dir = result.certs_dir
        ca = CertificateAuthority(ca_file=result.use_root,
                                  certs_dir=result.certs_dir,
                                  certname=result.name)

        created, host_filename = ca.get_cert_for_host(result.output_file,
                                                      overwrite)

        if created:
            print ('Created new cert "' + host_filename +
                   '" signed by root cert ' +
                   result.use_root)
        else:
            print ('Cert "' + host_filename + '" already exists,' +
                   ' use -f to overwrite')

    # Create new root certificate
    else:
        created, c, k = (CertificateAuthority.
                         generate_ca_root(result.output_file,
                                          result.name,
                                          overwrite))

        if created:
            print 'Created new root cert: "' + result.output_file + '"'
        else:
            print ('Root cert "' + result.output_file + '" already exists,' +
                    ' use -f to overwrite')

if __name__ == "__main__":
    main()
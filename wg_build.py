﻿import fileinput
import json
from subprocess import Popen
from utils import *


def wg_build(fasta_file, asktag, bowtie_path, ref_path):

    # ref_path is a string that containts the directory where the reference genomes are stored with
    # the input fasta filename appended
    ref_path = os.path.join(ref_path,
                            os.path.split(fasta_file)[1] + '_' + asktag)

    clear_dir(ref_path)
    #---------------------------------------------------------------
    # 1. First get the complementary genome (also do the reverse)
    # 2. Then do CT and GA conversions
    #---------------------------------------------------------------
    FW_genome={}
    header=""
    g=''
    n=0

    ref_log=open(os.path.join(ref_path, "log"),"w")

#    refd = shelve.open(ref_path + "refname.shelve",'n')

    refd = {}


    for line in fileinput.input(fasta_file):
        l=line.split()
        if line[0]!=">":
            g=g+line[:-1]
        elif line[0]==">":
            if header=="":
                n+=1
                header=l[0][1:]
                short_header=str(n).zfill(4)
            else:
                g=g.upper()
                print "reference seq: %s (renamed as %s ) %d bp"%(header,short_header,len(g))
                ref_log.write("reference seq: %s (renamed as %s ) %d bp"%(header,short_header,len(g))+"\n")
                refd[short_header]=[header,len(g)]
                FW_genome[short_header]=g

                g=""
                header=l[0][1:]
                n+=1
                short_header=str(n).zfill(4)

    g=g.upper()
    short_header=str(n).zfill(4)
    print "reference seq: %s (renamed as %s) %d bp"%(header,short_header,len(g))
    ref_log.write("reference seq: %s (renamed as %s ) %d bp"%(header,short_header,len(g))+"\n")
    refd[short_header]=[header,len(g)]
    FW_genome[short_header]=g
    g=""

    json.dump(refd, open(os.path.join(ref_path, 'refname.json'), 'w'))

#    refd.close()
    ref_log.close()

    FW_lst=FW_genome.keys()
    FW_lst.sort()

    #---------------- Python shelve -----------------------------------------------
    json.dump(FW_genome, open(os.path.join(ref_path, 'ref.json'), 'w'))

#    d = shelve.open(ref_path + "ref.shelve",'n')
#    for chr_id in FW_genome:
#        d[chr_id]=FW_genome[chr_id]
#    d.close()

    #---------------- Reverse complement (Crick strand) ----------------------------
    header=""
    RC_genome={}
    for header in FW_lst:
        g=FW_genome[header]
        g=reverse_compl_seq(g)
        RC_genome[header]=g
    RC_lst=RC_genome.keys()
    RC_lst.sort()


    if asktag=="Y":
        #---------------- 4 converted fasta -------------------------------------------

        outf=open(os.path.join(ref_path, 'W_C2T.fa'),'w')
        for header in FW_lst:
            outf.write('>%s\n' % header)
            g=FW_genome[header]
            g=g.replace("c","t")
            g=g.replace("C","T")
            outf.write('%s\n' % g)
        outf.close()
        print 'end 4-1'

        outf=open(os.path.join(ref_path, 'C_C2T.fa'),'w')
        for header in RC_lst:
            outf.write('>%s\n'% header)
            g=RC_genome[header]
            g=g.replace("c","t")
            g=g.replace("C","T")
            outf.write('%s\n'% g)
        outf.close()
        print 'end 4-2'

        outf=open(os.path.join(ref_path, 'W_G2A.fa'),'w')
        for header in FW_lst:
            outf.write('>%s\n'% header)
            g=FW_genome[header]
            g=g.replace("g","a")
            g=g.replace("G","A")
            outf.write('%s\n'% g)
        outf.close()
        print 'end 4-3'

        outf=open(os.path.join(ref_path, 'C_G2A.fa'),'w')
        for header in RC_lst:
            outf.write('>%s\n'% header)
            g=RC_genome[header]
            g=g.replace("g","a")
            g=g.replace("G","A")
            outf.write('%s\n' % g)
        outf.close()
        print 'end 4-4'
        #---------------- bowtie libraries -------------------------------------------
        to_bowtie = ['W_C2T', 'W_G2A', 'C_C2T', 'C_G2A']

    else: # asktag=="N"
        #---------------- 2 converted fasta -------------------------------------------

        outf=open(os.path.join(ref_path,'W_C2T.fa'),'w')
        for header in FW_lst:
            outf.write('>%s\n' % header)
            g=FW_genome[header]
            g=g.replace("c","t")
            g=g.replace("C","T")
            outf.write('%s\n' % g)
        outf.close()
        print 'end 2-1'

        outf=open(os.path.join(ref_path,'C_C2T.fa'),'w')
        for header in RC_lst:
            outf.write('>%s\n'% header)
            g=RC_genome[header]
            g=g.replace("c","t")
            g=g.replace("C","T")
            outf.write('%s\n'% g)
        outf.close()
        print 'end 2-2'
        to_bowtie = ['W_C2T', 'C_C2T']


    # start bowtie-build for all converted genomes and wait for the processes to finish
    for proc in [Popen('nohup %(bowtie_build)s -f %(fname)s.fa %(fname)s > %(fname)s.log'% {'bowtie_build'  : os.path.join(bowtie_path, 'bowtie-build'),
                                                                                            'fname'         : os.path.join(ref_path,fname) } ,
                       shell=True) for fname in to_bowtie]:
        proc.wait()

    # delete fasta files of converted genomes
    map(os.remove, map(lambda f: os.path.join(ref_path, f+'.fa'), to_bowtie))


    elapsed('Done')

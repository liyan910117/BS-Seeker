﻿import fileinput, os, time, random, math
from bs_utils.utils import *
from bs_align_utils import *

#----------------------------------------------------------------
# Read from the mapped results, return lists of unique / multiple-hit reads
# The function suppose at most 2 hits will be reported in single file
def extract_mapping(ali_file):
    unique_hits = {}
    non_unique_hits = {}

    header0 = ""
    lst = []

    for header, chr, location, no_mismatch, cigar in process_aligner_output(ali_file):
        #------------------------------
        if header != header0:
            #---------- output -----------
            if len(lst) == 1:
                unique_hits[header0] = lst[0]      # [no_mismatch, chr, location]
            elif len(lst) > 1:
                min_lst = min(lst, key = lambda x: x[0])
                max_lst = max(lst, key = lambda x: x[0])

                if min_lst[0] < max_lst[0]:
                    unique_hits[header0] = min_lst
                else:
                    non_unique_hits[header0] = min_lst[0]
                    #print "multiple hit", header, chr, location, no_mismatch, cigar # test
            header0 = header
            lst = [(no_mismatch, chr, location, cigar)]
        else: # header == header0, same header (readid)
            lst.append((no_mismatch, chr, location, cigar))

    if len(lst) == 1:
        unique_hits[header0] = lst[0]      # [no_mismatch, chr, location]
    elif len(lst) > 1:
        min_lst = min(lst, key = lambda x: x[0])
        max_lst = max(lst, key = lambda x: x[0])

        if min_lst[0] < max_lst[0]:
            unique_hits[header0] = min_lst
        else:
            non_unique_hits[header0] = min_lst[0]


    return unique_hits, non_unique_hits


def bs_single_end(main_read_file, asktag, adapter_file, cut1, cut2, no_small_lines, indexname, aligner_command, db_path, tmp_path, outfile, XS_pct, XS_count):
    #----------------------------------------------------------------
    # adapter : strand-specific or not
    adapter=""
    adapter_fw=""
    adapter_rc=""
    if adapter_file !="":
        adapter_inf=open(adapter_file,"r")
        if asktag == "N": #<--- directional library
            adapter=adapter_inf.readline()
            adapter_inf.close()
            adapter=adapter.rstrip("\n")
        elif asktag == "Y":#<--- undirectional library
            adapter_fw=adapter_inf.readline()
            adapter_rc=adapter_inf.readline()
            adapter_inf.close()
            adapter_fw=adapter_fw.rstrip("\n")
            adapter_rc=adapter_rc.rstrip("\n")
        adapter_inf.close()
    #----------------------------------------------------------------



    #----------------------------------------------------------------
    logm("Read filename: %s"% main_read_file )
    logm("Undirectional library: %s" % asktag )
    logm("The first base (for mapping): %d" % cut1)
    logm("The last base (for mapping): %d" % cut2)
    logm("Max. lines per mapping: %d"% no_small_lines)
    logm("Aligner: %s" % aligner_command)
    logm("Reference genome library path: %s" % db_path )
    logm("Number of mismatches allowed: %s" % indexname )
    if adapter_file !="":
        if asktag=="N":
            logm("Adapter to be removed from 3' reads: %s"%(adapter.rstrip("\n")))
        elif asktag=="Y":
            logm("Adapter to be removed from 3' FW reads: %s"%(adapter_fw.rstrip("\n")) )
            logm("Adapter to be removed from 3' RC reads: %s"%(adapter_rc.rstrip("\n")) )
    #----------------------------------------------------------------

    # helper method to join fname with tmp_path
    tmp_d = lambda fname: os.path.join(tmp_path, fname)

    db_d = lambda fname:  os.path.join(db_path, fname)

    #----------------------------------------------------------------
    # splitting the big read file

    input_fname = os.path.split(main_read_file)[1]

#    split_file(main_read_file, tmp_d(input_fname)+'-s-', no_small_lines)
#    my_files = sorted(splitted_file for splitted_file in os.listdir(tmp_path)
#                                            if splitted_file.startswith("%s-s-" % input_fname))

    #---- Stats ------------------------------------------------------------
    all_raw_reads=0
    all_trimed=0
    all_mapped=0
    all_mapped_passed=0

    numbers_premapped_lst=[0,0,0,0]
    numbers_mapped_lst=[0,0,0,0]

    mC_lst=[0,0,0]
    uC_lst=[0,0,0]


    no_my_files=0

    #----------------------------------------------------------------
    logm("== Start mapping ==")

    for read_file in isplit_file(main_read_file, tmp_d(input_fname)+'-s-', no_small_lines):
#    for read_file in my_files:
        original_bs_reads = {}
        no_my_files+=1
        random_id = ".tmp-"+str(random.randint(1000000,9999999))

        #-------------------------------------------------------------------
        # undirectional sequencing
        #-------------------------------------------------------------------
        if asktag=="Y":  

            #----------------------------------------------------------------
            outfile2=tmp_d('Trimed_C2T.fa'+random_id)
            outfile3=tmp_d('Trimed_G2A.fa'+random_id)

            outf2=open(outfile2,'w')
            outf3=open(outfile3,'w')

            #----------------------------------------------------------------
            # detect format of input file
            read_inf=open(read_file,"r")
            oneline=read_inf.readline()
            l=oneline.split()
            input_format=""
            if oneline[0]=="@":	# Illumina GAII FastQ (Lister et al Nature 2009)
                input_format="FastQ"
                n_fastq=0
            elif len(l)==1 and oneline[0]!=">": 	# pure sequences
                input_format="list of sequences"
            elif len(l)==11:	# Illumina GAII qseq file
                input_format="Illumina GAII qseq file"
            elif oneline[0]==">":	# fasta
                input_format="fasta"
                n_fasta=0
            read_inf.close()

            #----------------------------------------------------------------
            # read sequence, remove adapter and convert 
            id=""
            seq=""
            seq_ready="N"
            for line in fileinput.input(read_file):
                l=line.split()
                if input_format=="Old Solexa Seq file":
                    all_raw_reads+=1
                    id=str(all_raw_reads)
                    id=id.zfill(12)
                    seq=l[4]
                    seq_ready="Y"
                elif input_format=="list of sequences":
                    all_raw_reads+=1
                    id=str(all_raw_reads)
                    id=id.zfill(12)
                    seq=l[0]
                    seq_ready="Y"
                elif input_format=="FastQ":
                    m_fastq=math.fmod(n_fastq,4)
                    n_fastq+=1
                    seq_ready="N"
                    if m_fastq==0:
                        all_raw_reads+=1
                        id=str(all_raw_reads)
                        id=id.zfill(12)
                        seq=""
                    elif m_fastq==1:
                        seq=l[0]
                        seq_ready="Y"
                    else:
                        seq=""
                elif input_format=="Illumina GAII qseq file":
                    all_raw_reads+=1
                    id=str(all_raw_reads)
                    id=id.zfill(12)
                    seq=l[8]
                    seq_ready="Y"
                elif input_format=="fasta":
                    m_fasta=math.fmod(n_fasta,2)
                    n_fasta+=1
                    seq_ready="N"
                    if m_fasta==0:
                        all_raw_reads+=1
                        #id=str(all_raw_reads)
                        id=l[0][1:]
                        seq=""
                    elif m_fasta==1:
                        seq=l[0]
                        seq_ready="Y"
                    else:
                        seq=""

                #----------------------------------------------------------------
                if seq_ready=="Y":
                    seq=seq[cut1-1:cut2] #<----------------------selecting 0..52 from 1..72  -e 52
                    seq=seq.upper()
                    seq=seq.replace(".","N")

                    #--striping BS adapter from 3' read --------------------------------------------------------------
                    if (adapter_fw !="") and (adapter_rc !=""):
                        signature=adapter_fw[:6]
                        if signature in seq:
                            signature_pos=seq.index(signature)
                            if seq[signature_pos:] in adapter_fw:
                                seq=seq[:signature_pos]#+"".join(["N" for x in range(len(seq)-len(signature_pos))])
                                all_trimed+=1
                        else:
                            signature=adapter_rc[:6]
                            if signature in seq:
                                #print id,seq,signature
                                signature_pos=seq.index(signature)
                                if seq[signature_pos:] in adapter_rc:
                                    seq=seq[:signature_pos]#+"".join(["N" for x in range(len(seq)-len(signature_pos))])
                                    all_trimed+=1

                    if len(seq)<=4:
                        seq=''.join(["N" for x in xrange(cut2-cut1+1)])

                    #---------  trimmed_raw_BS_read  ------------------
                    original_bs_reads[id] = seq

                    #---------  FW_C2T  ------------------
                    outf2.write('>%s\n%s\n' % (id, seq.replace("C","T")))
                    #---------  RC_G2A  ------------------
                    outf3.write('>%s\n%s\n' % (id, seq.replace("G","A")))

            fileinput.close()

            outf2.close()
            outf3.close()

            delete_files(read_file)

           #--------------------------------------------------------------------------------
            # Bowtie mapping
            #-------------------------------------------------------------------------------
            WC2T=tmp_d("W_C2T_m"+indexname+".mapping"+random_id)
            CC2T=tmp_d("C_C2T_m"+indexname+".mapping"+random_id)
            WG2A=tmp_d("W_G2A_m"+indexname+".mapping"+random_id)
            CG2A=tmp_d("C_G2A_m"+indexname+".mapping"+random_id)

            print aligner_command % {'int_no_mismatches' : int_no_mismatches,
                                     'reference_genome' : os.path.join(db_path,'W_C2T'),
                                     'input_file' : outfile2,
                                     'output_file' : WC2T}

            run_in_parallel([ aligner_command % {'reference_genome' : os.path.join(db_path,'W_C2T'),
                                                   'input_file' : outfile2,
                                                   'output_file' : WC2T},

                              aligner_command % {'reference_genome' : os.path.join(db_path,'C_C2T'),
                                                   'input_file' : outfile2,
                                                   'output_file' : CC2T},

                              aligner_command % {'reference_genome' : os.path.join(db_path,'W_G2A'),
                                                   'input_file' : outfile3,
                                                   'output_file' : WG2A},

                              aligner_command % {'reference_genome' : os.path.join(db_path,'C_G2A'),
                                                   'input_file' : outfile3,
                                                   'output_file' : CG2A} ])


            delete_files(outfile2, outfile3)


            #--------------------------------------------------------------------------------
            # Post processing
            #--------------------------------------------------------------------------------

            FW_C2T_U,FW_C2T_R=extract_mapping(WC2T)
            RC_G2A_U,RC_G2A_R=extract_mapping(CG2A)

            FW_G2A_U,FW_G2A_R=extract_mapping(WG2A)
            RC_C2T_U,RC_C2T_R=extract_mapping(CC2T)

            #----------------------------------------------------------------
            # get uniq-hit reads
            #----------------------------------------------------------------
            Union_set=set(FW_C2T_U.iterkeys()) | set(RC_G2A_U.iterkeys()) | set(FW_G2A_U.iterkeys()) | set(RC_C2T_U.iterkeys())

            Unique_FW_C2T=set() # +
            Unique_RC_G2A=set() # +
            Unique_FW_G2A=set() # -
            Unique_RC_C2T=set() # -


            for x in Union_set:
                _list=[]
                for d in [FW_C2T_U, RC_G2A_U, FW_G2A_U, RC_C2T_U]:
                    mis_lst=d.get(x,[99])
                    mis=int(mis_lst[0])
                    _list.append(mis)
                for d in [FW_C2T_R, RC_G2A_R, FW_G2A_R, RC_C2T_R]:
                    mis=d.get(x,99) 
                    _list.append(mis)
                    # -- Bug fixed --
                    #if mis == 99 :
                    #   _list.append(mis)
                    # --- weilong ---
                    # the not-uniqued read occurrs at least twice in sigle file
                    # should report multiple hits if it holds the least value
                mini=min(_list)
                if _list.count(mini) == 1:
                    mini_index=_list.index(mini)
                    if mini_index == 0:
                        Unique_FW_C2T.add(x)
                    elif mini_index == 1:
                        Unique_RC_G2A.add(x)
                    elif mini_index == 2:
                        Unique_FW_G2A.add(x)
                    elif mini_index == 3:
                        Unique_RC_C2T.add(x)


            FW_C2T_uniq_lst=[[FW_C2T_U[u][1],u] for u in Unique_FW_C2T]
            FW_G2A_uniq_lst=[[FW_G2A_U[u][1],u] for u in Unique_FW_G2A]
            RC_C2T_uniq_lst=[[RC_C2T_U[u][1],u] for u in Unique_RC_C2T]
            RC_G2A_uniq_lst=[[RC_G2A_U[u][1],u] for u in Unique_RC_G2A]
            FW_C2T_uniq_lst.sort()
            RC_C2T_uniq_lst.sort()
            FW_G2A_uniq_lst.sort()
            RC_G2A_uniq_lst.sort()
            FW_C2T_uniq_lst=[x[1] for x in FW_C2T_uniq_lst]
            RC_C2T_uniq_lst=[x[1] for x in RC_C2T_uniq_lst]
            FW_G2A_uniq_lst=[x[1] for x in FW_G2A_uniq_lst]
            RC_G2A_uniq_lst=[x[1] for x in RC_G2A_uniq_lst]

            #----------------------------------------------------------------
            numbers_premapped_lst[0] += len(Unique_FW_C2T)
            numbers_premapped_lst[1] += len(Unique_RC_G2A)
            numbers_premapped_lst[2] += len(Unique_FW_G2A)
            numbers_premapped_lst[3] += len(Unique_RC_C2T)


            #----------------------------------------------------------------

            nn=0
            for ali_unique_lst, ali_dic in [(FW_C2T_uniq_lst,FW_C2T_U),
                                            (RC_G2A_uniq_lst,RC_G2A_U),
                                            (FW_G2A_uniq_lst,FW_G2A_U),
                                            (RC_C2T_uniq_lst,RC_C2T_U)]:
                nn += 1
                mapped_chr0 = ""
                for header in ali_unique_lst:

                    _, mapped_chr, mapped_location, cigar = ali_dic[header]

                    original_BS = original_bs_reads[header]
                    #-------------------------------------
                    if mapped_chr != mapped_chr0:
                        my_gseq = deserialize(db_d(mapped_chr))
                        chr_length = len(my_gseq)
                        mapped_chr0 = mapped_chr
                    #-------------------------------------

                    if nn == 2 or nn == 3:
                        cigar = list(reversed(cigar))
                    r_start, r_end, g_len = get_read_start_end_and_genome_length(cigar)


                    all_mapped += 1

                    if nn == 1: # +FW mapped to + strand:
                        FR = "+FW"
#                        mapped_location += 1
#                        origin_genome_long = my_gseq[mapped_location - 2 - 1 : mapped_location + g_len + 2 - 1]
                        mapped_strand="+"
#                        origin_genome=origin_genome_long[2:-2]

                    elif nn == 2:  # +RC mapped to + strand:
                        FR = "+RC" # RC reads from -RC reflecting the methylation status on Watson strand (+)

                        mapped_location = chr_length - mapped_location - g_len

#                        origin_genome_long = my_gseq[mapped_location - 2 - 1 : mapped_location + g_len + 2 - 1]
                        mapped_strand = "+"
#                        origin_genome = origin_genome_long[2:-2]

                        original_BS = reverse_compl_seq(original_BS)  # for RC reads

                    elif nn == 3:  						# -RC mapped to - strand:
                        mapped_strand = "-"
                        FR = "-RC" # RC reads from +RC reflecting the methylation status on Crick strand (-)

#                        mapped_location += 1
#                        origin_genome_long = my_gseq[mapped_location - 2 - 1 : mapped_location + g_len + 2 - 1]
#                        origin_genome_long = reverse_compl_seq(origin_genome_long)
#                        origin_genome = origin_genome_long[2:-2]
                        original_BS = reverse_compl_seq(original_BS)  # for RC reads

                    elif nn == 4: 						# -FW mapped to - strand:
                        mapped_strand = "-"
                        FR = "-FW"
                        mapped_location = chr_length - mapped_location - g_len

#                        origin_genome_long = my_gseq[mapped_location - 2 - 1 : mapped_location + g_len + 2 - 1]
#                        origin_genome_long = reverse_compl_seq(origin_genome_long)
#                        origin_genome = origin_genome_long[2:-2]


                    origin_genome, next, output_genome = get_genomic_sequence(my_gseq, mapped_location, mapped_location + g_len, mapped_strand)

                    r_aln, g_aln = cigar_to_alignment(cigar, original_BS, origin_genome)


                    if len(r_aln)==len(g_aln):
                        N_mismatch = N_MIS(r_aln, g_aln)
                        if N_mismatch <= int(indexname):
                            numbers_mapped_lst[nn-1] += 1
                            all_mapped_passed += 1
                            methy = methy_seq(r_aln, g_aln + next)
                            mC_lst, uC_lst = mcounts(methy, mC_lst, uC_lst)

                            #---STEVE FILTER----------------
                            condense_seq = methy.replace('-', '')
                            STEVE=0
                            if "ZZZ" in condense_seq:
                                STEVE=1
                            outfile.store(header, N_mismatch, FR, mapped_chr, mapped_strand, mapped_location, cigar, original_BS, methy, STEVE, output_genome = output_genome)

            #----------------------------------------------------------------
            logm("--> %s (%d) "%(read_file, no_my_files))
            delete_files(WC2T, WG2A, CC2T, CG2A)



        #--------------------------------------------------------------------
        # directional sequencing
        #--------------------------------------------------------------------

        if asktag=="N":  
            #----------------------------------------------------------------
            outfile2=tmp_d('Trimed_C2T.fa'+random_id)
            outf2=open(outfile2,'w')

            n=0
            #----------------------------------------------------------------
            read_inf=open(read_file,"r")
            oneline=read_inf.readline()
            l=oneline.split()
            input_format=""
            if oneline[0]=="@":	# Illumina GAII FastQ (Lister et al Nature 2009)
                input_format="Illumina GAII FastQ"
                n_fastq=0
            elif len(l)==1 and oneline[0]!=">": 	# pure sequences
                input_format="list of sequences"
            elif len(l)==11:	# Illumina GAII qseq file
                input_format="Illumina GAII qseq file"
            elif oneline[0]==">":	# fasta
                input_format="fasta"
                n_fasta=0
            read_inf.close()
            #print "detected data format: %s"%(input_format)
            #----------------------------------------------------------------
            id=""
            seq=""
            seq_ready="N"
            for line in fileinput.input(read_file):
                l=line.split()
                if input_format=="Old Solexa Seq file":
                    all_raw_reads+=1
                    id=str(all_raw_reads)
                    id=id.zfill(12)
                    seq=l[4]
                    seq_ready="Y"
                elif input_format=="list of sequences":
                    all_raw_reads+=1
                    id=str(all_raw_reads)
                    id=id.zfill(12)
                    seq=l[0]
                    seq_ready="Y"
                elif input_format=="Illumina GAII FastQ":
                    m_fastq=math.fmod(n_fastq,4)
                    n_fastq+=1
                    seq_ready="N"
                    if m_fastq==0:
                        all_raw_reads+=1
                        id=str(all_raw_reads)
                        id=id.zfill(12)
                        seq=""
                    elif m_fastq==1:
                        seq=l[0]
                        seq_ready="Y"
                    else:
                        seq=""
                elif input_format=="Illumina GAII qseq file":
                    all_raw_reads+=1
                    id=str(all_raw_reads)
                    id=id.zfill(12)
                    seq=l[8]
                    seq_ready="Y"
                elif input_format=="fasta":
                    m_fasta=math.fmod(n_fasta,2)
                    n_fasta+=1
                    seq_ready="N"
                    if m_fasta==0:
                        all_raw_reads+=1
                        id=l[0][1:]
                        seq=""
                    elif m_fasta==1:
                        seq=l[0]
                        seq_ready="Y"
                    else:
                        seq=""

                #----------------------------------------------------------------
                if seq_ready=="Y":
                    seq=seq[cut1-1:cut2] #<----------------------selecting 0..52 from 1..72  -e 52
                    seq=seq.upper()
                    seq=seq.replace(".","N")

                    #--striping adapter from 3' read --------------------------------------------------------------
                    if adapter !="":
                        signature=adapter[:6]
                        if signature in seq:
                            signature_pos=seq.index(signature)
                            if seq[signature_pos:] in adapter:
                                seq=seq[:signature_pos]#+"".join(["N" for x in range(len(seq)-len(signature_pos))])
                                all_trimed+=1
                    if len(seq)<=4:
                        seq = "N" * (cut2-cut1+1)

                    #---------  trimmed_raw_BS_read  ------------------
                    original_bs_reads[id] = seq


                    #---------  FW_C2T  ------------------
                    outf2.write('>%s\n%s\n' % (id, seq.replace("C","T")))

            fileinput.close()

            outf2.close()
            delete_files(read_file)

            #--------------------------------------------------------------------------------
            # Bowtie mapping
            #--------------------------------------------------------------------------------
            WC2T=tmp_d("W_C2T_m"+indexname+".mapping"+random_id)
            CC2T=tmp_d("C_C2T_m"+indexname+".mapping"+random_id)

            run_in_parallel([ aligner_command % {'reference_genome' : os.path.join(db_path,'W_C2T'),
                                                  'input_file' : outfile2,
                                                  'output_file' : WC2T},
                              aligner_command % {'reference_genome' : os.path.join(db_path,'C_C2T'),
                                                  'input_file' : outfile2,
                                                  'output_file' : CC2T} ])

            delete_files(outfile2)

            #--------------------------------------------------------------------------------
            # Post processing
            #--------------------------------------------------------------------------------


            FW_C2T_U, FW_C2T_R = extract_mapping(WC2T)
            RC_C2T_U, RC_C2T_R = extract_mapping(CC2T)

            #----------------------------------------------------------------
            # get uniq-hit reads
            #----------------------------------------------------------------
            Union_set = set(FW_C2T_U.iterkeys()) | set(RC_C2T_U.iterkeys())

            Unique_FW_C2T = set() # +
            Unique_RC_C2T = set() # -


            for x in Union_set:
                _list=[]
                for d in [FW_C2T_U,RC_C2T_U]:
                    mis_lst=d.get(x,[99])
                    mis=int(mis_lst[0])
                    _list.append(mis)
                for d in [FW_C2T_R,RC_C2T_R]:
                    mis=d.get(x,99)
                    _list.append(mis)
                    # -- Bug fixed --
                    #if mis == 99 :
                    #   _list.append(mis)
                    # --- weilong ---
                    # the not-uniqued read occurrs at least twice in sigle file
                    # should report multiple hits if it holds the least value
                mini=min(_list)
                if _list.count(mini)==1:
                    mini_index=_list.index(mini)
                    if mini_index==0:
                        Unique_FW_C2T.add(x)
                    elif mini_index==1:
                        Unique_RC_C2T.add(x)


            FW_C2T_uniq_lst=[[FW_C2T_U[u][1],u] for u in Unique_FW_C2T]
            RC_C2T_uniq_lst=[[RC_C2T_U[u][1],u] for u in Unique_RC_C2T]
            FW_C2T_uniq_lst.sort()
            RC_C2T_uniq_lst.sort()
            FW_C2T_uniq_lst=[x[1] for x in FW_C2T_uniq_lst]
            RC_C2T_uniq_lst=[x[1] for x in RC_C2T_uniq_lst]


            #----------------------------------------------------------------

            numbers_premapped_lst[0] += len(Unique_FW_C2T)
            numbers_premapped_lst[1] += len(Unique_RC_C2T)

            #----------------------------------------------------------------

            nn = 0
            for ali_unique_lst, ali_dic in [(FW_C2T_uniq_lst,FW_C2T_U),(RC_C2T_uniq_lst,RC_C2T_U)]:
                nn += 1
                mapped_chr0 = ""
                for header in ali_unique_lst:

                    _, mapped_chr, mapped_location, cigar = ali_dic[header]

                    original_BS = original_bs_reads[header]
                    #-------------------------------------
                    if mapped_chr != mapped_chr0:
                        my_gseq = deserialize(db_d(mapped_chr))
                        chr_length = len(my_gseq)
                        mapped_chr0 = mapped_chr
                    #-------------------------------------

                    r_start, r_end, g_len = get_read_start_end_and_genome_length(cigar)

                    all_mapped+=1
                    if nn == 1: 	# +FW mapped to + strand:
                        FR = "+FW"
#                        mapped_location += 1
#                        origin_genome_long = my_gseq[mapped_location - 2 - 1 : mapped_location + g_len + 2 - 1]
                        mapped_strand = "+"
#                        origin_genome = origin_genome_long[2:-2]


                    elif nn == 2: 	# -FW mapped to - strand:
                        mapped_strand = "-"
                        FR = "-FW"
                        mapped_location = chr_length - mapped_location - g_len
#                        origin_genome_long = my_gseq[mapped_location - 2 - 1 : mapped_location + g_len + 2 - 1]
#                        origin_genome_long = reverse_compl_seq(origin_genome_long)
#                        origin_genome = origin_genome_long[2:-2]


                    origin_genome, next, output_genome = get_genomic_sequence(my_gseq, mapped_location, mapped_location + g_len, mapped_strand)
                    r_aln, g_aln = cigar_to_alignment(cigar, original_BS, origin_genome)

                    if len(r_aln) == len(g_aln):

                        N_mismatch = N_MIS(r_aln, g_aln) #+ original_BS_length - (r_end - r_start) # mismatches in the alignment + soft clipped nucleotides

                        if N_mismatch <= int(indexname):

                            numbers_mapped_lst[nn-1] += 1

                            all_mapped_passed += 1

                            methy = methy_seq(r_aln, g_aln+next)

                            mC_lst, uC_lst = mcounts(methy, mC_lst, uC_lst)

                            ##---STEVE FILTER----------------
                            #condense_seq=methy.replace('-', '')
                            ##STEVE = 0
                            ##if "ZZZ" in condense_seq:
                            ##    STEVE = 1

                            #---XS FILTER----------------
                            #XS = 1 if "ZZZ" in methy.replace('-', '') else 0
                            XS = 0
			    nCH = methy.count('y') + methy.count('z')
                            nmCH = methy.count('Y') + methy.count('Z')
                            if( (nmCH>XS_count) and nmCH/float(nCH+nmCH)>XS_pct ) :
                                XS = 1


                            outfile.store(header, N_mismatch, FR, mapped_chr, mapped_strand, mapped_location, cigar, original_BS, methy, XS, output_genome = output_genome)

            #----------------------------------------------------------------
            logm("--> %s (%d) "%(read_file,no_my_files))
            delete_files(WC2T, CC2T)


    #----------------------------------------------------------------

#    outf.close()
    delete_files(tmp_path)

    logm("Number of raw reads: %d \n"% all_raw_reads)
    if all_raw_reads >0:
        logm("Number of reads having adapter removed: %d \n" % all_trimed )
        logm("Number of unique-hits reads for post-filtering: %d\n" % all_mapped)
        if asktag=="Y":
            logm(" ---- %7d FW reads mapped to Watson strand (before post-filtering)"%(numbers_premapped_lst[0]) )
            logm(" ---- %7d RC reads mapped to Watson strand (before post-filtering)"%(numbers_premapped_lst[1]) )
            logm(" ---- %7d FW reads mapped to Crick strand (before post-filtering)"%(numbers_premapped_lst[2]) )
            logm(" ---- %7d RC hreads mapped to Crick strand (before post-filtering)"%(numbers_premapped_lst[3]) )
        elif asktag=="N":
            logm(" ---- %7d FW reads mapped to Watson strand (before post-filtering)"%(numbers_premapped_lst[0]) )
            logm(" ---- %7d FW reads mapped to Crick strand (before post-filtering)"%(numbers_premapped_lst[1]) )

        logm("Post-filtering %d uniqlely aligned reads with mismatches <= %s"%(all_mapped_passed, indexname) )
        if asktag=="Y":
            logm(" ---- %7d FW reads mapped to Watson strand"%(numbers_mapped_lst[0]) )
            logm(" ---- %7d RC reads mapped to Watson strand"%(numbers_mapped_lst[1]) )
            logm(" ---- %7d FW reads mapped to Crick strand"%(numbers_mapped_lst[2]) )
            logm(" ---- %7d RC reads mapped to Crick strand"%(numbers_mapped_lst[3]) )
        elif asktag=="N":
            logm(" ---- %7d FW reads mapped to Watson strand"%(numbers_mapped_lst[0]) )
            logm(" ---- %7d FW reads mapped to Crick strand"%(numbers_mapped_lst[1]) )
        logm("Mapability= %1.4f%%"%(100*float(all_mapped_passed)/all_raw_reads) )

        n_CG=mC_lst[0]+uC_lst[0]
        n_CHG=mC_lst[1]+uC_lst[1]
        n_CHH=mC_lst[2]+uC_lst[2]

        logm("----------------------------------------------" )
        logm("Methylated C in mapped reads ")

        logm(" mCG %1.3f%%"%((100*float(mC_lst[0])/n_CG) if n_CG != 0 else 0))
        logm(" mCHG %1.3f%%"%((100*float(mC_lst[1])/n_CHG) if n_CHG != 0 else 0))
        logm(" mCHH %1.3f%%"%((100*float(mC_lst[2])/n_CHH) if n_CHH != 0 else 0))

        
#    logm("----------------------------------------------" )
    logm("------------------- END --------------------" )
    elapsed("=== END %s ===" % main_read_file)




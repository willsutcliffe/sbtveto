#!/usr/bin/env python
"""Script to format signal+Muinduced Background data file for NN studies.
SBT response for each signal candidate is combined with a randomly chosen EMBG file on an MC level (and then digitised) .
"""

import ROOT
import uproot
import numpy as np
from rootpyPickler import Unpickler
import os
import csv
from argparse import ArgumentParser
import shipunit as u
pdg = ROOT.TDatabasePDG.Instance()
import random

parser = ArgumentParser();
parser = ArgumentParser(description=__doc__);
parser.parse_args()


class EventDataProcessor:
    def __init__(self, input_path,signal_path, output_dir):
        self.input_path = input_path
        self.signal_path= signal_path
        self.geo_file=None #will be updated according to the signal_file
        self.output_dir = output_dir
        self.global_file_index = 0
        self.global_event_id = 0
        self.inputmatrix = []
        self.truth = [] 
        self.signal_decaychannel={}
        self.detList = None  # Placeholder for cached SBT cell map
        

    def choose_embg_file(self):

        self.retry=True
        while self.retry: 

            inputFolders = [inp for inp in os.listdir(self.input_path) if os.path.isdir(os.path.join(self.input_path, inp))]
            inputFolder = random.choice(inputFolders)
            inputFolderPath=os.path.join(self.input_path, inputFolder)
        
            subFolders = [sub for sub in os.listdir(inputFolderPath) if os.path.isdir(os.path.join(inputFolderPath, sub))]
            
            if subFolders: 
                
                randomSubFolder = random.choice(subFolders)
                randomSubFolderPath = os.path.join(inputFolderPath, randomSubFolder)
                self.embg_file=os.path.join(randomSubFolderPath, "ship.conical.MuonBack-TGeant4.root")
                f = ROOT.TFile.Open(self.embg_file,"read")
                try:
                    embg_tree = f.cbmsim
                    print(f"Processing MuonInduced BG file:\n{self.embg_file}\n\tEntries: {embg_tree.GetEntries()}")
                    self.retry=False
                except:
                    pass 
        f.Close()

    def load_geofile(self):
        """
        Load the geometry file and set the global geometry manager.
        """
        try:
            fgeo = ROOT.TFile(self.geo_file)  
            self.fGeo = fgeo.FAIRGeom  
            ROOT.gGeoManager = self.fGeo  

            upkl    = Unpickler(fgeo)
            self.ShipGeo = upkl.load('ShipGeo')
            print(f"Loaded geometry file: {self.geo_file}")
        except Exception as e:
            raise FileNotFoundError(f"Error loading geo file: {self.geo_file}. Error: {e}")

    def SBTcell_map(self): #provides a cell map with index in [0,853] for each cell.

        if self.detList is not None:
            return  # If the map is already built, no need to rebuild
        try:
            fGeo = ROOT.gGeoManager
            detList = {}
            LiSC = fGeo.GetTopVolume().GetNode('DecayVolume_1').GetVolume().GetNode('T2_1').GetVolume().GetNode('VetoLiSc_0')
            index = -1
            for LiSc_cell in LiSC.GetVolume().GetNodes():
                index += 1
                name = LiSc_cell.GetName()
                detList[index] = name[-6:]
            return detList
        except Exception as e:
            print(e)

    def printMCTrack(self,n,MCTrack):
           mcp = MCTrack[n]
           try: print(' %6s %10s %12i %6.3F %6.3F %7.3F %7.3F %7.3F %7.3F %6s %10.3F'%(n,pdg.GetParticle(mcp.GetPdgCode()).GetName(),mcp.GetPdgCode(),mcp.GetPx()/u.GeV,mcp.GetPy()/u.GeV,mcp.GetPz()/u.GeV, \
                              mcp.GetStartX()/u.m,mcp.GetStartY()/u.m,mcp.GetStartZ()/u.m,mcp.GetMotherId(),mcp.GetWeight()    ))
           except: 
                print(' %6s %10s %12i %6.3F %6.3F %7.3F %7.3F %7.3F %7.3F %6s %10.3F'%(n,"----",mcp.GetPdgCode(),mcp.GetPx()/u.GeV,mcp.GetPy()/u.GeV,mcp.GetPz()/u.GeV, \
                              mcp.GetStartX()/u.m,mcp.GetStartY()/u.m,mcp.GetStartZ()/u.m,mcp.GetMotherId(),mcp.GetWeight()    ))

    def dump(self,event,pcut,print_whole_event=True):

           if print_whole_event:
               print('\n %6s %10s %12s %6s %6s %7s %7s %7s %7s %6s %10s'%('#','particle','pid','px','py','pz','vx','vy','vz','mid','w'))
               print(' %6s %10s %12s %6s %6s %7s %7s %7s %7s %6s %10s\n '%(' ','--------','---','--','--','--','--','--','--','---','---'))
           n=-1
           daughters=[]
           for mcp in event.MCTrack: 
             n+=1
             if mcp.GetP()/u.GeV < pcut :  continue
             if print_whole_event: self.printMCTrack(n,event.MCTrack)
             
             if mcp.GetMotherId()==-1:
                try: mother=pdg.GetParticle(mcp.GetPdgCode()).GetName()
                except: mother='----'
             if mcp.GetMotherId()==0: daughters.append(pdg.GetParticle(mcp.GetPdgCode()).GetName())
           
           return daughters

    def ImpactParameter(self,point,tPos,tMom):
      t = 0
      if hasattr(tMom,'P'): P = tMom.P()
      else:                 P = tMom.Mag()
      for i in range(3):   t += tMom(i)/P*(point(i)-tPos(i)) 
      dist = 0
      for i in range(3):   dist += (point(i)-tPos(i)-t*tMom(i)/P)**2
      dist = ROOT.TMath.Sqrt(dist)
      return dist #in cm

    def define_weight(self,event_weight,SHiP_running=5):
        
        #event_weight=number of muon events per spill

        nPOTinteraction     =(2.e+20)*(SHiP_running/5)
        nPOTinteraction_perspill =5.e+13
        n_Spill  = nPOTinteraction/nPOTinteraction_perspill #number of spill in 5 years
        return event_weight*n_Spill
        
    def make_outputfile(self, filenumber):

        inputmatrix = np.array(self.inputmatrix)
        truth       = np.array(self.truth)
        
        rootfilename    = f"{self.output_dir}datafile_EMBG_{filenumber}_{self.global_file_index}.root"

        file = uproot.recreate(rootfilename)
        file["tree"] = {
                        "inputmatrix": inputmatrix,
                        "truth": truth
                        }

        print(f"\n\nFiles formatted and saved in {rootfilename}")
        self.global_file_index += 1
        self.inputmatrix = []
    
    def define_t_vtx(self,sTree,candidate):
          
          t0=sTree.ShipEventHeader.GetEventTime()
          
          candidatePos = ROOT.TLorentzVector()
          candidate.ProductionVertex(candidatePos)

          d1, d2 = candidate.GetDaughter(0), candidate.GetDaughter(1)        
          d1_mc, d2_mc = sTree.fitTrack2MC[d1], sTree.fitTrack2MC[d2]                   

          time_vtx_from_strawhits=[]        

          for hit in sTree.strawtubesPoint:            

             if not (int( str( hit.GetDetectorID() )[:1]) ==1 or int( str( hit.GetDetectorID() )[:1]) ==2) : continue #if hit.GetZ() > ( ShipGeo.TrackStation2.z + 0.5*(ShipGeo.TrackStation3.z - ShipGeo.TrackStation2.z) ): continue #starwhits only from T1 and T2 before the SHiP magnet .

             if not (hit.GetTrackID()==d1_mc or hit.GetTrackID()==d2_mc) : continue
               
             t_straw    = hit.GetTime()
             d_strawhit  = [hit.GetX(),hit.GetY(),hit.GetZ()]

             dist     = np.sqrt( (candidatePos.X()-hit.GetX() )**2+( candidatePos.Y() -hit.GetY())**2+ ( candidatePos.Z()-hit.GetZ() )**2) #distance to the vertex #in cm            

             Mom          = sTree.MCTrack[hit.GetTrackID()].GetP()/u.GeV
             mass         = sTree.MCTrack[hit.GetTrackID()].GetMass()
             v            = u.c_light*Mom/np.sqrt(Mom**2+(mass)**2)

             t_vertex   = t_straw-(dist/v)

             time_vtx_from_strawhits.append(t_vertex)
              
          t_vtx=np.average(time_vtx_from_strawhits)+t0   

          return t_vtx  
    
    def process_event(self, signal_event,embg_event,Digi_SBTHits):

        detList = self.SBTcell_map()
        energy_array = np.zeros(854)
        time_array = np.full(854, -9999) #default value is -9999
        
        for track in embg_event.MCTrack: 
                if track.GetPdgCode() in [-13,13]:
                        weight_i=self.define_weight(track.GetWeight())#<---weight over 5 years   (track.GetWeight()<---per spill)

        for aDigi in Digi_SBTHits.values():
            detID = str(aDigi.GetDetectorID())
            ID_index = [lastname for lastname, firstname in detList.items() if firstname == detID][0]
            energy_array[ID_index] = aDigi.GetEloss()
            time_array[ID_index] = aDigi.GetTDC()


        #nHits=len(embg_event.UpstreamTaggerPoint)
        
        for signal in signal_event.Particles:    
                    
            signalPos = ROOT.TLorentzVector()
            signal.ProductionVertex(signalPos)
            
            inv_mass = signal.GetMass()
            signalMom = ROOT.TLorentzVector()
            signal.Momentum(signalMom)
            Target_Point = ROOT.TVector3(0, 0, self.ShipGeo.target.z0)
            Impact_par = self.ImpactParameter(Target_Point, signalPos, signalMom)

            track_1, track_2 = signal.GetDaughter(0), signal.GetDaughter(1)

            fitStatus_1 = signal_event.FitTracks[track_1].getFitStatus()
            D1_chi2ndf = fitStatus_1.getChi2() / fitStatus_1.getNdf()
            D1_mom = signal_event.FitTracks[track_1].getFittedState().getMom().Mag()

            fitStatus_2 = signal_event.FitTracks[track_2].getFitStatus()
            D2_chi2ndf = fitStatus_2.getChi2() / fitStatus_2.getNdf()
            D2_mom = signal_event.FitTracks[track_2].getFittedState().getMom().Mag()

            candidate_details = np.array([
                len(signal_event.Particles),
                signal.GetMass(),
                signal.GetDoca(),
                Impact_par,
                D1_chi2ndf,
                D2_chi2ndf,
                fitStatus_1.getNdf(),
                fitStatus_2.getNdf(),
                D1_mom,
                D2_mom
            ])
            
            vertexposition = np.array([signalPos.X(), signalPos.Y(), signalPos.Z()])
            
            t_vtx=self.define_t_vtx(signal_event,signal)

            self.inputmatrix.append(np.concatenate(
                                                   (energy_array,
                                                    time_array,
                                                    vertexposition,
                                                    np.array(t_vtx),#np.array(nHits),
                                                    np.array(weight_i)
                                                    ,candidate_details
                                                    )
                                                    , axis=None
                                                    ) )# inputmatrix has shape (nEvents,size of inputarray)
            
            self.truth.append(0)
            self.global_event_id+=1

        
    def digitizeSBT(self,embg_vetoPoints,signal_vetoPoints,signal_t0):
        
        ElossPerDetId    = {}
        tOfFlight        = {}
        #listOfVetoPoints = {}
        digiSBT={}
        key=-1
         
        for vetoPoints in [embg_vetoPoints,signal_vetoPoints]:
            for aMCPoint in vetoPoints:
                key+=1
                detID=aMCPoint.GetDetectorID()
                Eloss=aMCPoint.GetEnergyLoss()
                if detID not in ElossPerDetId:
                    ElossPerDetId[detID]=0
                    #listOfVetoPoints[detID]=[]
                    tOfFlight[detID]=[]
                ElossPerDetId[detID] += Eloss
                #listOfVetoPoints[detID].append(key)
                tOfFlight[detID].append(aMCPoint.GetTime())
        
        index=0 
        for detID in ElossPerDetId:
                    
            aHit = ROOT.vetoHit(detID,ElossPerDetId[detID])
            aHit.SetTDC(min( tOfFlight[detID] )+ signal_t0 )    
            if ElossPerDetId[detID]<0.045:    aHit.setInvalid()  
            digiSBT[index] = aHit
            index=index+1
        return digiSBT

    def process_file(self):
        
        self.choose_embg_file() 

        Total_events=0
        Success=0
        Total_files=len(os.listdir(self.signal_path))

        
        f_embg = ROOT.TFile.Open(self.embg_file,"read")
        embg_tree = f_embg.cbmsim
        embg_entries= embg_tree.GetEntries()

        for ntuple_list in os.listdir(self.signal_path):
            
            if "ship.conical.EvtCalc-TGeant4_rec.root" not in os.listdir(os.path.join(self.signal_path,ntuple_list)): continue
            
            f = ROOT.TFile.Open(os.path.join(self.signal_path,ntuple_list,"ship.conical.EvtCalc-TGeant4_rec.root"))
            
            try:
                signal_tree = f.cbmsim
                if self.geo_file==None:
                    self.geo_file=os.path.join(self.signal_path,ntuple_list,'geofile_full.conical.EvtCalc-TGeant4.root')
                    self.load_geofile()
                #print(f"File read:{os.path.join(self.signal_path,ntuple_list,'ship.conical.EvtCalc-TGeant4_rec.root')} successfully.\n")
                Success+=1
            except Exception as e:
                #print(f"Error in file:{os.path.join(self.signal_path,ntuple_list,'ship.conical.EvtCalc-TGeant4_rec.root')}\n\t{e}")
                continue
            nEvents = signal_tree.GetEntries()

            Total_events+=nEvents

            for eventNr,signal_event in enumerate(signal_tree):
                
                daughters=self.dump(signal_event,0,print_whole_event=False)
                sorted_daughters = tuple(sorted(daughters))


                if sorted_daughters!=('mu+', 'mu-', 'nu_e') or len(signal_event.Particles)==0: continue
                
                signal_t0=signal_event.ShipEventHeader.GetEventTime()

                random_index = random.randint(0,embg_entries - 1)
                embg_tree.GetEntry(random_index)
                combined_Digi_SBThits=self.digitizeSBT(embg_tree.vetoPoint,signal_event.vetoPoint,signal_t0)
                

                if not combined_Digi_SBThits: continue #only look for events with SBT activity
                
                if sorted_daughters not in self.signal_decaychannel:
                    self.signal_decaychannel[sorted_daughters]=0
                self.signal_decaychannel[sorted_daughters]+=1

                print(f"Signal Event{eventNr}\t {self.global_event_id} ---> {len(signal_event.Particles)} reconst. particle(s) in event")
                self.process_event(signal_event,embg_tree,combined_Digi_SBThits)


        for channel, details in self.signal_decaychannel.items():
            print(f"Decay Channel: {channel} {details} Events")
        #print(f"\n\n Total Files Available:{Total_files}, cbmsim found only in {Success} files")
        
        filenumber=0
        self.make_outputfile(filenumber)

    def read_outputdata(self):

        inputmatrixlist,truthlist=[],[]
            
        for datafile in os.listdir(self.output_dir):

            if not datafile.startswith("datafile_EMBG_"): continue
                        
            tree = uproot.open(self.output_dir+datafile)["tree"]
            data = tree.arrays(['inputmatrix', 'truth'], library='np')
            
            inputmatrix     = data['inputmatrix']
            truth           = data['truth'] 
            
            inputmatrixlist.append(inputmatrix)
            truthlist.append(truth)

        inputmatrix = np.concatenate(inputmatrixlist)
        truth = np.concatenate(truthlist)
        print(f"\n\nNumber of events available:{len(inputmatrix)} ")
        print(f"\nTest print event 0:\n------------------------------------------")
        print("Number of SBThits:", np.count_nonzero(inputmatrix[0][:854]),"/",len(inputmatrix[0][:854]))
        print("\tshould match timing entries:",np.sum(inputmatrix[0][854:1708] != -9999),"/",len(inputmatrix[0][854:1708]))
        print("\nvertexposition",inputmatrix[0][1708:1711])
        print("\nVertex time:",inputmatrix[0][1711],"ns")
        print("\nEvent weight:",inputmatrix[0][1712]," over 5 years")
        
        signal_details=inputmatrix[0][1713:]
        print("\nOther Candidate details:")
        print(f"\tlen(sTree.Particles)\t{signal_details[0]}")
        print(f"\tsignal.GetMass()\t{signal_details[1]}")
        print(f"\tsignal.GetDoca()\t{signal_details[2]}")
        print(f"\tImpact_par\t{signal_details[3]}")
        print(f"\tDaughter1_chi2ndf\t{signal_details[4]}")
        print(f"\tDaughter2_chi2ndf\t{signal_details[5]}")
        print(f"\tfitStatus_Daughter1.getNdf()\t{signal_details[6]}")
        print(f"\tfitStatus_Daughter2.getNdf()\t{signal_details[7]}")
        print(f"\tDaughter1_mom\t{signal_details[8]}")
        print(f"\tDaughter2_mom\t{signal_details[9]}")


embg_path='/eos/experiment/ship/simulation/bkg/MuonBack_2024helium/sc_v6_10_spills' 

signalfile_path="/eos/experiment/ship/simulation/sig/HNL/helium/inclusive/Ntuples/"

processor = EventDataProcessor(input_path=embg_path , signal_path= signalfile_path, output_dir="./")

processor.process_file()
processor.read_outputdata()
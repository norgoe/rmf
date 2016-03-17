#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import numpy as np
import time
import matplotlib.pyplot as plt
import csv
import gpspipetocsv

T_GUARD = 0.050   #50ms guard time

def checkOutOfOrderInner(strippedSortedSubArray):
	'''Returns true if the chirp/packet sorted list has received packets out of their normal ordering'''
	ret = False;
	size = strippedSortedSubArray.size
	lasttrx_ns = strippedSortedSubArray[0]['trxns']
	for x in xrange(1,size -1):
		if lasttrx_ns > strippedSortedSubArray[x]['trxns']:
			return True

def storeTupleListToCsv(tupleList,fileoutname) :
	'''Store the Tuplelist in the given filename as a csv'''
	print 'Storing ',len(tupleList),' lines in ',fileoutname
	with open(fileoutname, "w") as outFile:
	    #csv.register_dialect("custom", delimiter=",", skipinitialspace=True)
	    #writer = csv.writer(outFile, dialect="custom")
	    writer = csv.writer(outFile)
	    for row in tupleList:
	        writer.writerow(row)
	    outFile.flush()
	return

class NodeLogs:
	"""Class loading and holding all rmf log files of a node"""

	def __init__(self, role, directory, DEBUG=False):
		self.role = role
		self.directory = directory
		self.chirpdata = []
		os.chdir(directory)
		self.loadLogs(DEBUG)
		self.calculateChirpDetails(DEBUG)
		if self.role == 'server':
			fileoutname = self.directory+'/upstream-data.csv'
		else:
			fileoutname = self.directory+'/downstream-data.csv'
		storeTupleListToCsv(self.chirpdata,fileoutname)

	def loadLogs(self,DEBUG) :
		print('Reading '+self.role+' logfiles')
		self.mSenderRawData   = np.genfromtxt(self.role+'.mSenderRawData', dtype=None, delimiter=',', names=True) 
		if DEBUG: print self.mSenderRawData.dtype.names
		self.mReceiverRawData = np.genfromtxt(self.role+'.mReceiverRawData', dtype=None, delimiter=',', names=True) 
		if DEBUG: print self.mReceiverRawData.dtype.names
		# self.mReceiverDelay   = np.genfromtxt(self.role+'.mReceiverDelay', dtype=None, delimiter=',', names=True, skip_header=1)
		# if DEBUG: print self.mReceiverDelay.dtype.names
		# self.mReceiverDatarate   = np.genfromtxt(self.role+'.mReceiverDatarate', dtype=None, delimiter=',', names=True, skip_header=1)
		# if DEBUG: print self.mReceiverDatarate.dtype.names
		# self.mReceiverGaps    = np.genfromtxt(self.role+'.mReceiverGaps', dtype=None, delimiter=',', names=True, skip_header=2) 
		# if DEBUG: print self.mReceiverGaps.dtype.names
		# self.mReceiverNewTtx  = np.genfromtxt(self.role+'.mReceiverNewTtx', dtype=None, delimiter=',', names=True, skip_header=1) 
		# if DEBUG: print self.mReceiverNewTtx.dtype.names
		# self.sReceiverData    = np.genfromtxt(self.role+'.sReceiverData', dtype=None, delimiter=',', names=True) 
		# if DEBUG: print self.sReceiverData.dtype.names
		# self.sSenderData      = np.genfromtxt(self.role+'.sSenderData', dtype=None, delimiter=',', names=True) 
		# if DEBUG: print self.sSenderData.dtype.names
		return




	def calculateChirpDetails(self,DEBUG=False) :
		minChirp = min(self.mReceiverRawData['Chirp'])
		maxChirp = max(self.mReceiverRawData['Chirp'])
		chirpCountsReceived = np.bincount(self.mReceiverRawData['Chirp'])
		#todo we are still missing the information about the send packets
		lastChirp = 0
		lastPacket = 0;
		#loss = np.empty_like(self.mReceiverRawData)
		self.chirpdata.append( ('chirp','#send','#arrived','#arrivedOnce','#duplicates','packetsize [Bytes]','loss rate %','data rate [Byte/s]','delay [ns]',
			'first ttx [ns]','first trx [ns]','last ttx [ns]','delta trx [s]','t_gap_i [s]'))
		firstofachirpindex = np.argmax(self.mReceiverRawData['Pack'] > 0)
		sizeOfFirstPacket = self.mReceiverRawData['BytePacket'][0]
		reverseOrder = self.mReceiverRawData[::-1]
		length = len(reverseOrder)
		lastlastpacket = self.mReceiverRawData[0] #take the first packet as a dummy

		#iterate to all the arrived chirps
		for x in xrange(minChirp,maxChirp):
			idx_firstPacketOfChirpX = np.argmax(self.mReceiverRawData['Chirp'] >= x )			#index of first received packet of chirp x
			idx_lastPacketOfChirpX = length - np.argmax(reverseOrder['Chirp'] <= x )     		#index of last  received packet of chirp x
			firstPacket = self.mReceiverRawData[idx_firstPacketOfChirpX] 						#first received packet of chirp x
			lastPacket = self.mReceiverRawData[(idx_lastPacketOfChirpX-1)] 						#last  received packet of chirp x
			subArray = self.mReceiverRawData[idx_firstPacketOfChirpX:idx_lastPacketOfChirpX:1]  #array containing all packets of chirp x plus probably out of order packets of other chirps

			if len(subArray)==0:
				print 'chirp ',x,'was completely lost, do something better than just adding -1 to everything'
				#self.chirpdata.append( ('Chirp','#send','#arrived','#arrivedOnce','#duplicates','Packetsize [Bytes]','Lossrate %','data rate [Byte/s]','delay [ns]','first ttx [ns]','first trx [ns]','last ttx [ns]','delta trx [s], t_gap [s]'))
				self.chirpdata.append( (x       ,   0   ,    -1    ,     0        ,       0     ,          0         ,float('nan'),    float('nan')    ,float('nan'),        -1      ,       -1       ,     -1        ,  0.0         , float('nan') ))
			else:
				if firstPacket['Chirp']!=lastPacket['Chirp'] and DEBUG:
					print idx_firstPacketOfChirpX,'/',idx_lastPacketOfChirpX,' ',firstPacket['Chirp'],':',firstPacket['Pack'],' / ',lastPacket['Chirp'],':',lastPacket['Pack']
					print subArray

				sortedSubArray = subArray[subArray[['Chirp','Pack']].argsort()]                     #sorted array of the subarray by chirp,packet
				idx_start = np.argmax(sortedSubArray['Chirp'] >= x )								#indexes of packet 1 and packet n of chirp x in the sorted array
				idx_end = np.argmax(sortedSubArray['Chirp'] >= (x+1))
				if idx_end==0:
					idx_end = len(sortedSubArray)
				strippedSortedSubArray = sortedSubArray[idx_start : idx_end :1]						#just the packets of chirp x sorted by chirp,packet
				arrived = len(strippedSortedSubArray)												#arrived packets of chirp x (with duplicates)
				if arrived==0:
					print 'chirp ',x,'was completely lost, do something better than just adding -1 to everything'
					#self.chirpdata.append( ('Chirp','#send','#arrived','#arrivedOnce','#duplicates','Packetsize [Bytes]','Lossrate %','data rate [Byte/s]','delay [ns]','first ttx [ns]','first trx [ns]','last ttx [ns]','delta trx [s], t_gap [s]'))
					self.chirpdata.append( (x       ,   0   ,    -1    ,     0        ,       0     ,          0         ,float('nan'),    float('nan')    ,float('nan'),        -1      ,       -1       ,     -1        ,  0.0         , float('nan') ))
				else:
					packetbins = np.bincount(strippedSortedSubArray['Pack'])
					lost_ArrivedOnce_Duplicates = np.bincount(packetbins[1:len(packetbins):1])  		
					lost = lost_ArrivedOnce_Duplicates[0]												#[0] stores the number of lost packets
					arrivedOnce = lost_ArrivedOnce_Duplicates[1]										#[1] stores the number of packets which arrived once
					duplicates = arrived - arrivedOnce 													

					outOfOrderOuter =  not (arrived == len(subArray))									#did packets of other chirps arrive during reception of chirp x
					outOfOrderInner = checkOutOfOrderInner(strippedSortedSubArray)		                #did the packets of this chirp arrive in correct ordering

					#if lost > 0 or duplicates >0:
					if DEBUG and duplicates >0: # for debug purposes print the subarrays for chipr x
						print 'x, idx_firstPacketOfChirpX, idx_lastPacketOfChirpX ',x, idx_firstPacketOfChirpX, idx_lastPacketOfChirpX
						print subArray
						print '-----------------------------'
						print sortedSubArray
						print 'idx_start,idx_end,outOfOrderOuter ',idx_start,idx_end, outOfOrderOuter
						print '*****************************'
						print strippedSortedSubArray
						print '#############################'
						print packetbins
						print lost_ArrivedOnce_Duplicates
						print 'send,arrivedOnce,duplicates,lost ', firstPacket['Pack_1'],  arrivedOnce, duplicates, lost
						print '======================================'
					
					firstttx_ns = int(firstPacket['ttx_firstns'])   											#transmit time of first arrived packet of chirp x
					firsttrx_ns = int(firstPacket['trxns'])														#receive  time of first arrived packet of chirp x
					lastttx_ns = int(lastPacket['ttxns'])														#transmit time of last  arrived packet of chirp x
					lasttrx_ns = int(lastPacket['trxns'])														#receive  time of last  arrived packet of chirp x

					total = int(firstPacket['Pack_1'])															#number of send packets of chirp x
					lossrate = float( (100.0* (total - arrivedOnce))/total )    								#lossrate for the chirp (cleaned from duplicates and out of order)
					packsize = int(lastPacket['BytePacket'])													#the size of the packets of chirp x (the first might be smaller)

					t_gap_i=float(firsttrx_ns-lastlastpacket['trxns'])/1000000000.0	    						#the gap between chirp x and chirp x-1

					#check t_gap_i before using delay!
					if t_gap_i >= T_GUARD and firstPacket['Pack'] <=5: 
						delay_ns = float(firstPacket['trxns'] - firstPacket['ttxns'])/1000000000.0				#the delay of the first received packet of the chirp
					else:
						delay_ns = float('nan')																	#the delay of the first received packet of the chirp
						if DEBUG: print 'chirp=',x,' lastchirp=',lastlastpacket['Chirp'],' t_gap_i=',t_gap_i

					# FIXME check datarate calculation															#data rate and delta_trx for chirp x
					if arrivedOnce >=2: 
						deltatrx_s = (int(lastPacket['trxns']) - int(firstPacket['trxns']))/1000000000.0
						datarate = int( (arrivedOnce - 1.0) * packsize / deltatrx_s)
					else:
						#todo fixme
						datarate = float('nan')
						deltatrx_s = float('nan')

					#self.chirpdata.append( ('chirp','#send','#arrived','#arrivedOnce','#duplicates','packetsize [Bytes]','loss rate %','data rate [Byte/s]','delay [ns]','first ttx [ns]','first trx [ns]','last ttx [ns]','delta trx [s]','t_gap_i [s]'))
					self.chirpdata.append( (x,total,arrived,arrivedOnce,duplicates,packsize,lossrate,datarate,delay_ns,firstttx_ns,firsttrx_ns,lastttx_ns,lasttrx_ns,deltatrx_s,t_gap_i))

					lastlastpacket = lastPacket

		#print chirpdata
		return

		
		plottable = zip(*chirpdata)
		plt.step(plottable[0],plottable[4]) #lossrate
		plt.twinx().step(plottable[0],plottable[5],'yx') #datarate
		
		return


directories = [r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150619/182357',
				r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150619/221143']
#directories = [ r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150616/093334',
#directories = [				r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150616/103403' ]
				# r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150619/064105',
				# r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150618/082259',
				# r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150610/081751' ]
#directories = [ r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150615/172315', 
# directories = [			  	r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150616/093334',
#			  	r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150616/103403' ]
#directories = [ r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150611/080304' ]
#directories = [ r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150610/081751' ]
# directories = [ r'/home/goebel/rmf-logs-to-keep/t530lan/20150610/001736' ,
# 				r'/home/goebel/rmf-logs-to-keep/t530lan/20150610/003441',
# 				r'/home/goebel/rmf-logs-to-keep/t530lan/20150610/004518']
#directories = [ r'/home/goebel/rmf/results/mTBUS/192.168.10.50_to_134.99.147.228/20150609-233421' ]
#directories = [ r'/home/goebel/rmf/results/mTBUS/192.168.2.184_to_134.99.147.228/20150609-175154' ]
#directories = [ r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150609/075436' ]
				# r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150608/072115',
				# r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150608/080325' ]

# directories = [ r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150527/083805' , 
# 				r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150602/072522',
# 				r'/home/goebel/rmf-logs-to-keep/alix1-strongrom/20150602/093359' ]	

for directory in directories: 
	logs = NodeLogs('server',directory,False)
	logs2 = NodeLogs('client',directory,False)
	gpspipetocsv.convertGpsdlogToCsv(directory)


plt.show()


# for x in np.nditer(logs.mReceiverRawData):
# 	if x['Chirp']

# timeit np.argmax(aa>N/2)
# timeit np.where(aa>N/2)[0][0]
# timeit np.nonzero(aa>N/2)[0][0]

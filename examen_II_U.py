# -*- coding: utf-8 -*-
"""
Created on Mon Aug 15 14:19:02 2022

@author: Usuario
"""
from tkinter import messagebox
import  tkinter  as  tk
from tkinter.messagebox import showinfo
from tkinter import filedialog 
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import os
import snappy
from snappy import Product
from snappy import ProductIO
from snappy import ProductUtils
from snappy import WKTReader
from snappy import HashMap
from snappy import GPF
# Para leer shapefiles
import shapefile
import pygeoif
import  tkinter  as  tk
from tkinter.messagebox import showinfo
from tkinter import filedialog 

ventana  =  tk.Tk()
ventana.geometry("350x600")

ventana.config(bg="gray")
ventana.title("Calculo de Zonas Inundadas")



#Leer y mostrar la informaciónd de la imagen
#width = product.getSceneRasterWidth()
#print("Width: {} px".format(width))
#height = product.getSceneRasterHeight()
# #print("Height: {} px".format(height))
# name = product.getName()
# print("Name: {}".format(name))
# band_names = product.getBandNames()
# print("Band names: {}".format(", ".join(band_names)))

def abrirarchivos ():
    global archivo
    archivo = filedialog.askopenfilename(title="Seleccionar Archivo .zip", initialdir="C:/", filetypes=(("Archivos comprimidos", ".zip"),))
    caja0.insert(tk.END, archivo) 
    return(archivo)

def abrirshape ():
    global shape
    shape = filedialog.askopenfilename(title="Seleccionar Archivo .shp", initialdir="C:/", filetypes=(("Archivos shape de ESRI", ".shp"),))
    caja1.insert(tk.END, shape) 
    return(shape)

def plotBand(product, band, vmin, vmax):
    global chart
    try: 
       chart.get_tk_widget().destroy()
    except: 
        pass
    band = product.getBand(band)
    w = band.getRasterWidth()
    h = band.getRasterHeight()
    print(w, h)
    band_data = np.zeros(w * h, np.float32)
    band.readPixels(0, 0, w, h, band_data)
    band_data.shape = h, w
    width = 12
    height = 12
    plt.figure(figsize=(width, height))
    imgplot = plt.imshow(band_data, cmap=plt.cm.binary, vmin=vmin, vmax=vmax)
    return imgplot
    
        

##PRE-PROCESAMIENTO
def preprocesamiento():
    messagebox.showinfo(message="La imagen esta siendo procesada", title="´Preproceso de Imagen")
    ###LEER LOS DATOS DE LA IMAGEN
   # Cargar imagenes
    path_to_sentinel_data = archivo
    product = ProductIO.readProduct(path_to_sentinel_data)
    ##Aplicar correccion orbital
    HashMap = snappy.jpy.get_type('java.util.HashMap')
    parameters = HashMap()
    GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()
    parameters.put('orbitType', 'Sentinel Precise (Auto Download)')
    parameters.put('polyDegree', '3')
    parameters.put('continueOnFail', 'false')
    apply_orbit_file = GPF.createProduct('Apply-Orbit-File', parameters, product)

    ##Recortar la imagen
    r = shapefile.Reader(shape)
    g=[]
    for s in r.shapes():
        g.append(pygeoif.geometry.as_shape(s))
        m = pygeoif.MultiPoint(g)
        wkt = str(m.wkt).replace("MULTIPOINT", "POLYGON(") + ")"
        
        #Usar el shapefile para cortar la imagen
        SubsetOp = snappy.jpy.get_type('org.esa.snap.core.gpf.common.SubsetOp')
        bounding_wkt = wkt
        geometry = WKTReader().read(bounding_wkt)
        HashMap = snappy.jpy.get_type('java.util.HashMap')
        GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()
        parameters = HashMap()
        parameters.put('copyMetadata', True)
        parameters.put('geoRegion', geometry)
        product_subset = snappy.GPF.createProduct('Subset', parameters, apply_orbit_file)
        
    # #Mostrar las dimensiones de la imagen
    # width = product_subset.getSceneRasterWidth()
    # print("Width: {} px".format(width))
    # height = product_subset.getSceneRasterHeight()
    # print("Height: {} px".format(height))
    # band_names = product_subset.getBandNames()
    # print("Band names: {}".format(", ".join(band_names)))
    # band = product_subset.getBand(band_names[0])
    # print(band.getRasterSize())
    # plotBand(product_subset, "Intensity_VV", 0, 100000)
        
    ##Aplicar la calibracion de la imagen
    parameters = HashMap()
    parameters.put('outputSigmaBand', True)
    parameters.put('sourceBands', 'Intensity_VV')
    parameters.put('selectedPolarisations', "VV")
    parameters.put('outputImageScaleInDb', False)
    product_calibrated = GPF.createProduct("Calibration", parameters, product_subset)
    plotBand(product_calibrated, "Sigma0_VV", 0, 1)
    
    ##Aplicar el filtro Speckle
    filterSizeY = '5'
    filterSizeX = '5'
    parameters = HashMap()
    parameters.put('sourceBands', 'Sigma0_VV')
    parameters.put('filter', 'Lee')
    parameters.put('filterSizeX', filterSizeX)
    parameters.put('filterSizeY', filterSizeY)
    parameters.put('dampingFactor', '2')
    parameters.put('estimateENL', 'true')
    parameters.put('enl', '1.0')
    parameters.put('numLooksStr', '1')
    parameters.put('targetWindowSizeStr', '3x3')
    parameters.put('sigmaStr', '0.9')
    parameters.put('anSize', '50')
    speckle_filter = snappy.GPF.createProduct('Speckle-Filter', parameters, product_calibrated)
    plotBand(speckle_filter, 'Sigma0_VV', 0, 1)
    
    ##Aplicar la correccion del terremo
    parameters = HashMap()
    parameters.put('demName', 'SRTM 3Sec')
    parameters.put('pixelSpacingInMeter', 10.0)
    parameters.put('sourceBands', 'Sigma0_VV')
    global speckle_filter_tc
    speckle_filter_tc = GPF.createProduct("Terrain-Correction", parameters, speckle_filter)
    plotBand(speckle_filter_tc, 'Sigma0_VV', 0, 0.1)

    print("fin")    
    #Crear una mascara binaria para la inundacion
def umbral ():
    parameters = HashMap()
    BandDescriptor = snappy.jpy.get_type('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor')
    targetBand = BandDescriptor()
    targetBand.name = 'Sigma0_VV_Flooded'
    targetBand.type = 'uint8'
    valor1=caja3.get()
    targetBand.expression = f'(Sigma0_VV < {valor1} ? 1 : 0)'
    targetBands = snappy.jpy.array('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor', 1)
    targetBands[0] = targetBand
    parameters.put('targetBands', targetBands)
    global flood_mask
    flood_mask = GPF.createProduct('BandMaths', parameters, speckle_filter_tc)
    plotBand(flood_mask, 'Sigma0_VV_Flooded', 0, 1)
    
    print ("fin")

# def plotBand(product, band, vmin, vmax):
        
#         band = product.getBand(band)
#         w = band.getRasterWidth()
#         h = band.getRasterHeight()
#         print(w, h)
#         band_data = np.zeros(w * h, np.float32)
#         band.readPixels(0, 0, w, h, band_data)
#         band_data.shape = h, w
#         width = 12
#         height = 12
#         out_image = plt.figure(figsize=(width, height))
#         imgplot = plt.imshow(band_data, cmap=plt.cm.binary, vmin=vmin, vmax=vmax)
#         chart = FigureCanvasTkAgg(out_image, ventana)
#         chart.get_tk_widget().pack()

#Crear la imagen a partir de la mascara
def salida ():
    ProductIO.writeProduct(flood_mask, caja0.get, 'GeoTIFF')
    os.path.exists('final_mask.tif')
    messagebox.showinfo(message="La imagen se ha descargado", title="Descarga de Imagen")
    # img=ventana.PhotoImage(file=flood_mask)
    # labelimagen=ventana.Label(ventana, image=img)
    # labelimagen.pack(row=15)
    print ("fin") 

label0=tk.Label (ventana, text="1. Selecciona la Imagen a utilizar", bg='yellow')
label0.grid(row= 0, column=2, pady=1)
boton0=tk.Button(ventana, text="Buscar Imagen", bg='white', command=abrirarchivos)
boton0.grid(row=1, column=2, pady=2)
caja0=tk.Entry(ventana, width=50)
caja0.grid(row= 2, column=2, pady=5)

label1=tk.Label (ventana, text="2. Seleccione el shapefile de la zona a analizar", bg='yellow')
label1.grid(row= 4, column=2)
boton1=tk.Button(ventana, text="Buscar Shapefile", bg='white', command=abrirshape)
boton1.grid(row=5, column=2, pady=2)
caja1=tk.Entry(ventana, width=50)
caja1.grid(row= 6, column=2, pady=5)

label2=tk.Label (ventana, text="3. Procede a Preprocesar la Imagen", bg='yellow')
label2.grid(row= 7, column=2)
boton2=tk.Button(ventana, text="PreProcesar Imagen", bg='white', command=preprocesamiento)
boton2.grid(row=8, column=2, pady=5)

label3=tk.Label (ventana, text="4. Defina el umbral para la mascara de agua", bg='yellow')
label3.grid(row= 9, column=2)
boton3=tk.Button(ventana, text="Aplicar Mascara", bg='white', command=umbral)
boton3.grid(row=11, column=2, pady=2)
caja3=tk.Entry(ventana)
caja3.grid(row= 10, column=2, pady=5)

label4=tk.Label (ventana, text="5. Crea la imagen GeoTiff a partir del umbral seleccionado", bg='yellow')
label4.grid(row= 12, column=2)
boton4=tk.Button(ventana, text="Crear Archivo", bg='white', command=salida)
boton4.grid(row=13, column=2, pady=5)

ventana.mainloop()
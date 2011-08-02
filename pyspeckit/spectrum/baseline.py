import numpy as np
import matplotlib

interactive_help_message = """
Left-click twice to select or add to the baseline fitting range.  Middle or
right click to disconnect and perform the fit.
"""

class Baseline:
    def __init__(self,Spectrum):
        self.baselinepars  = None
        self.order = None
        self.basespec = np.zeros(Spectrum.data.shape[0])
        self.excludemask = np.zeros(Spectrum.data.shape[0],dtype='bool')
        self.OKmask = np.ones(Spectrum.data.shape[0],dtype='bool')
        self.Spectrum = Spectrum
        self.specplotter = Spectrum.plotter
        self.blleg = None
        self.click = 0
        self.nclicks_b1 = 0
        self.nclicks_b2 = 0
        self.fitregion=[]
        self.excludevelo = []
        self.excludepix  = []
        self.subtracted = False
        self.bx1 = 0
        self.bx2 = Spectrum.data.shape[0] - 1
        self.include = [self.bx1,self.bx2]
        self.includevelo = [Spectrum.xarr[self.bx1],Spectrum.xarr[self.bx2]]
        self.powerlaw=False

    def __call__(self, order=1, annotate=False, excludefit=False, save=True,
            exclude=None, exclusionlevel=0.01, interactive=False, 
            LoudDebug=False, fit_original=True, **kwargs):
        """
        Fit and remove a polynomial from the spectrum.  
        It will be saved in the variable "self.basespec"
        and the fit parameters will be saved in "self.order"

        function baseline(spectrum,xarr=None,xmin=None,xmax=None,order=1,quiet=True,exclude=None):
        Subtract a baseline from a spectrum
        If xmin,xmax are not specified, defaults to ignoring first and last 10% of spectrum

        exclude is a set of start/end indices to ignore when baseline fitting
        (ignored by setting error to infinite in fitting procedure)

        excludefit creates a mask based on the fitted gaussian model (assuming
        that it has a zero-height) using an exclusion level of (exclusionlevel)
        * the smallest gaussian peak that was fit

        if fit_original is set, "basespec" is added back to the spectrum before
        fitting so you can run this procedure multiple times without losing
        information
        """
        if LoudDebug:
            print "Range: %i:%i" % (self.bx1,self.bx2)
            print "Excluded: %i" % (self.excludemask.sum())
        specfit = self.Spectrum.specfit
        self.order = order
        fitp = np.zeros(self.order+1)
        if self.subtracted and fit_original: # add back in the old baseline
            self.spectofit = self.Spectrum.data+self.basespec
        else:
            self.spectofit = np.copy(self.Spectrum.data)
        self.OKmask = (self.spectofit==self.spectofit)
        if exclude == 'interactive' or interactive:
            self.specplotter.axis.set_autoscale_on(False)
            print interactive_help_message
            self.excludemask[:] = True # exclude everything
            self.excludevelo = []
            self.excludepix  = []
            self.includevelo = []
            self.includepix  = []
            selectregion_interactive = lambda(x): self.selectregion_interactive(x,**kwargs)
            self.click = self.specplotter.axis.figure.canvas.mpl_connect('button_press_event',selectregion_interactive)
        else:
            self.selectregion(**kwargs)
            if excludefit and specfit.modelpars is not None:
                #vlo = self.specplotter.specfit.modelpars[1] - 2*self.specplotter.specfit.modelpars[2]
                #vhi = self.specplotter.specfit.modelpars[1] + 2*self.specplotter.specfit.modelpars[2]
                #exclude = [np.argmin(abs(self.Spectrum.xarr-vlo)),argmin(abs(self.Spectrum.xarr-vhi))]
                specfit.fullsizemodel() # make sure the spectrum is the right size
                self.excludemask = abs(specfit.model) > exclusionlevel*abs(min(specfit.modelpars[0::3]))
            else:
                self.excludemask[:] = False
            self.dofit(exclude=exclude,annotate=annotate,fit_original=fit_original,**kwargs)
        if save: self.savefit()
        if LoudDebug:
            print "Range: %i:%i" % (self.bx1,self.bx2)
            print "Excluded: %i" % (self.excludemask.sum())

    def dofit(self, exclude=None, excludeunits='velo', annotate=False,
            include=None, includeunits='velo', 
            subtract=True, fit_original=False, powerlaw=False, **kwargs):
        """
        Do the baseline fitting and save and plot the results.

        Can specify a region to exclude using velocity units or pixel units
        """
        if include is not None and includeunits in ['velo','km/s','wavelength','frequency']:
            self.excludemask[:] = True
            if len(include) % 2 == 0:
                self.includevelo = include
                self.includepix = []
                for vl,vu in zip(include[::2],include[1::2]):
                    xl = np.argmin(abs(self.Spectrum.xarr-vl))
                    xu = np.argmin(abs(self.Spectrum.xarr-vu))
                    if xl > xu: xl,xu=xu,xl
                    self.excludemask[xl:xu] = False
                    self.includepix += [xl,xu]
        elif include is not None and includeunits in ['pix','pixel','chan','channel']:
            self.excludemask[:] = True
            if len(include) % 2 == 0:
                self.includepix = []
                for xl,xu in zip(include[::2],include[1::2]):
                    if xl > xu: xl,xu=xu,xl
                    self.excludemask[xl:xu] = False
                    self.includepix += [xl,xu]
        else:
            self.includepix = []
            self.includevelo = []
        if exclude is not None and excludeunits in ['velo','km/s','wavelength','frequency']:
            if len(exclude) % 2 == 0:
                self.excludevelo = exclude
                self.excludepix = []
                for vl,vu in zip(exclude[::2],exclude[1::2]):
                    xl = np.argmin(abs(self.Spectrum.xarr-vl))
                    xu = np.argmin(abs(self.Spectrum.xarr-vu))
                    if xl > xu: xl,xu=xu,xl
                    self.excludemask[xl:xu] = True
                    self.excludepix += [xl,xu]
        elif exclude is not None and excludeunits in ['pix','pixel','chan','channel']:
            if len(exclude) % 2 == 0:
                self.excludepix = []
                for xl,xu in zip(exclude[::2],exclude[1::2]):
                    if xl > xu: xl,xu=xu,xl
                    self.excludemask[xl:xu] = True
                    self.excludepix += [xl,xu]
        else:
            self.excludepix = []
            self.excludevelo = []

        self.basespec, self.baselinepars = self._baseline(
                self.spectofit[self.bx1:self.bx2],
                xarr=self.Spectrum.xarr[self.bx1:self.bx2],
                order=self.order, exclude=None, 
                mask=(True-self.OKmask[self.bx1:self.bx2])+self.excludemask[self.bx1:self.bx2],
                powerlaw=powerlaw,
                **kwargs)
        # create the full baseline spectrum...
        if powerlaw:
            self.powerlaw = True
            self.basespec = (self.baselinepars[0]*self.Spectrum.xarr**(-self.baselinepars[1])).squeeze()
        else:
            self.powerlaw = False
            self.basespec = np.poly1d(self.baselinepars)(self.Spectrum.xarr)
        if subtract:
            if self.subtracted and fit_original: 
                # use the spectrum with the old baseline added in (that's what we fit to)
                self.Spectrum.data = self.spectofit - self.basespec
            else:
                self.Spectrum.data -= self.basespec
            self.subtracted = True
        else:
            self.subtracted = False

        if self.specplotter.axis is not None:
            self.plot_baseline()

    def plot_baseline(self, annotate=True, plotcolor='orange'):

        # clear out the errorplot.  This should not be relevant...
        if self.specplotter.errorplot is not None: 
            for p in self.specplotter.errorplot:
                if isinstance(p,matplotlib.collections.PolyCollection):
                    if p in self.specplotter.axis.collections: self.specplotter.axis.collections.remove(p)
                if isinstance(p,matplotlib.lines.Line2D):
                    if p in self.specplotter.axis.lines: self.specplotter.axis.lines.remove(p)

        # if we subtract the baseline, replot the now-subtracted data with rescaled Y axes
        if self.subtracted:
            if self.specplotter.axis is not None: 
                for p in self.specplotter.axis.lines:
                    self.specplotter.axis.lines.remove(p)
            plotmask = self.OKmask*False
            plotmask[self.bx1:self.bx2] = self.OKmask[self.bx1:self.bx2]
            self.specplotter.ymin = abs(self.Spectrum.data[plotmask].min())*1.1*np.sign(self.Spectrum.data[plotmask].min())
            self.specplotter.ymax = abs(self.Spectrum.data[plotmask].max())*1.1*np.sign(self.Spectrum.data[plotmask].max())
            self.specplotter.plot()
        else: # otherwise just overplot the fit
            self.specplotter.axis.set_autoscale_on(False)
            self.specplotter.axis.plot(self.Spectrum.xarr,self.basespec,color=plotcolor)

        if annotate: self.annotate() # refreshes automatically
        elif self.specplotter.autorefresh: self.specplotter.refresh()

    def selectregion_interactive(self,event,**kwargs):
        """
        select regions for baseline fitting
        """
        toolbar = self.specplotter.figure.canvas.manager.toolbar
        if toolbar.mode == '':
            if hasattr(event,'button'):
                if event.button == 1:
                    if self.nclicks_b1 == 0:
                        self.bx1 = np.argmin(abs(event.xdata-self.Spectrum.xarr))
                        self.includevelo += [self.Spectrum.xarr[self.bx1]]
                        self.includepix  += [self.bx1]
                        self.nclicks_b1 += 1
                    elif self.nclicks_b1 == 1:
                        self.bx2 = np.argmin(abs(event.xdata-self.Spectrum.xarr))
                        self.nclicks_b1 -= 1
                        if self.bx1 > self.bx2: self.bx1,self.bx2 = self.bx2,self.bx1
                        self.fitregion += self.specplotter.axis.plot(
                                self.Spectrum.xarr[self.bx1:self.bx2],
                                self.Spectrum.data[self.bx1:self.bx2]+self.specplotter.offset,
                                drawstyle='steps-mid',
                                color='g',alpha=0.5)
                        self.specplotter.refresh()
                        self.excludemask[self.bx1:self.bx2] = False
                        self.includevelo += [self.Spectrum.xarr[self.bx2]]
                        self.includepix  += [self.bx2]
                if event.button in [2,3]:
                    self.specplotter.figure.canvas.mpl_disconnect(self.click)
                    self.dofit(**kwargs)
                    for p in self.fitregion:
                        p.set_visible(False)
                        if p in self.specplotter.axis.lines: self.specplotter.axis.lines.remove(p)
                    self.fitregion=[] # I should be able to just remove from the list... but it breaks the loop...
                    self.specplotter.refresh()
            elif hasattr(event,'key'):
                if event.key == '?':
                    print interactive_help_message

    def selectregion(self,xmin=None,xmax=None,xtype='wcs', highlight=False, **kwargs):
        """
        Pick a fitting region in either WCS units or pixel units
        """
        if xmin is not None and xmax is not None:
            if xtype in ('wcs','WCS','velo','velocity','wavelength','frequency','freq','wav'):
                self.bx1 = np.argmin(abs(xmin-self.Spectrum.xarr))
                self.bx2 = np.argmin(abs(xmax-self.Spectrum.xarr))
            else:
                self.bx1 = xmin
                self.bx2 = xmax
        elif self.specplotter.xmin is not None and self.specplotter.xmax is not None:
            self.bx1 = np.argmin(abs(self.specplotter.xmin-self.Spectrum.xarr))
            self.bx2 = np.argmin(abs(self.specplotter.xmax-self.Spectrum.xarr))
        else:
            self.bx1 = 0
            self.bx2 = self.Spectrum.data.shape[0]
            #raise ValueError("Need to input xmin and xmax, or have them set by plotter, for selectregion.")
        if self.bx1>self.bx2: self.bx1,self.bx2 = self.bx2,self.bx1
        if highlight:
            self.fitregion += self.specplotter.axis.plot(
                    self.Spectrum.xarr[self.bx1:self.bx2],
                    self.Spectrum.data[self.bx1:self.bx2]+self.specplotter.offset,
                    drawstyle='steps-mid',
                    color='g',alpha=0.5)

    def annotate(self,loc='upper left'):
        if self.powerlaw:
            bltext = "bl: $y=%6.3gx^{-%6.3g}$" % (self.baselinepars[0],self.baselinepars[1])
        else:
            bltext = "bl: $y=$"+"".join(["$%+6.3gx^{%i}$" % (f,self.order-i)
                for i,f in enumerate(self.baselinepars)])
        #self.blleg = text(xloc,yloc     ,bltext,transform = self.specplotter.axis.transAxes)
        self.clearlegend()
        pl = matplotlib.collections.CircleCollection([0],edgecolors=['k'])
        self.blleg = self.specplotter.axis.legend(
                (pl,),
                (bltext,),loc=loc,markerscale=0.001,
                borderpad=0.1, handlelength=0.1, handletextpad=0.1
                )
        self.specplotter.axis.add_artist(self.blleg)
        if self.specplotter.autorefresh: self.specplotter.refresh()
  
    def clearlegend(self):
        if self.blleg is not None: 
            self.blleg.set_visible(False)
            if self.blleg in self.specplotter.axis.artists:
                self.specplotter.axis.artists.remove(self.blleg)
        if self.specplotter.autorefresh: self.specplotter.refresh()

    def savefit(self):
        if self.baselinepars is not None and hasattr(self.Spectrum,'header'):
            for ii,p in enumerate(self.baselinepars):
                self.Spectrum.header.update('BLCOEF%0.2i' % (ii),p,comment="Baseline power-law best-fit coefficient x^%i" % (self.order-ii-1))

    def _baseline(self,spectrum,xarr=None,xmin='default',xmax='default',order=1,quiet=True,exclude=None,
            mask=None, powerlaw=False, **kwargs):
        """
        Subtract a baseline from a spectrum
        If xmin,xmax are not specified, defaults to ignoring first and last 10% of spectrum
        *unless* order > 1, in which case ignoring the ends tends to cause strange effects

        exclude is a set of start/end indices to ignore when baseline fitting
        (ignored by setting error to infinite in fitting procedure)
        """
        if xmin == 'default':
            if order <= 1 and exclude is None: xmin = np.floor( spectrum.shape[-1]*0.1 )
            else:          xmin = 0
        elif xmin is None:
            xmin = 0
        if xmax == 'default':
            if order <= 1 and exclude is None: xmax = np.ceil( spectrum.shape[-1]*0.9 )
            else:          xmax = spectrum.shape[-1]
        elif xmax is None:
            xmax = spectrum.shape[-1]
        
        if xarr is None:
            xarr = np.indices(spectrum.shape).squeeze()

        subxarr = xarr[xmin:xmax]
        if powerlaw:
            pguess = [1,1]

            def mpfitfun(data,err):
                def f(p,fjac=None): return [0,np.ravel(((p[0] * subxarr**(-p[1]))-data)/err)]
                return f
        else:
            pguess = [0]*(order+1)

            def mpfitfun(data,err):
                def f(p,fjac=None): return [0,np.ravel((np.poly1d(p)(subxarr)-data)/err)]
                return f

        err = np.ones(spectrum.shape)
        if exclude is not None:
            err[exclude[0]:exclude[1]] = 1e10
        if mask is not None:
            if mask.dtype.name != 'bool': mask = mask.astype('bool')
            err[mask] = 1e10
            if hasattr(spectrum,'mask'):
                spectrum.mask=mask
        if (spectrum!=spectrum).sum() > 0:
            print "There is an error in baseline: some values are NaN"
            import pdb; pdb.set_trace()

        import mpfit
        mp = mpfit.mpfit(mpfitfun(spectrum[xmin:xmax],err[xmin:xmax]),xall=pguess,quiet=quiet,**kwargs)
        fitp = mp.params
        if powerlaw:
            bestfit = (fitp[0]*xarr**(-fitp[1])).squeeze()
        else:
            bestfit = np.poly1d(fitp)(xarr).squeeze()

        return bestfit,fitp

    def crop(self,x1pix,x2pix):
        """
        When spectrum.crop is called, this must be too
        """
        self.basespec = self.basespec[x1pix:x2pix]
        self.excludemask = self.excludemask[x1pix:x2pix]
        self.OKmask = self.OKmask[x1pix:x2pix]

    def downsample(self,factor):
        self.basespec = self.basespec[::factor]
        self.excludemask = self.excludemask[::factor]
        self.OKmask = self.OKmask[::factor]


import torch
import torch.nn as nn
import torch.nn.functional as F

class GaussianBlur(nn.Module):
    def __init__(self, channels,reduction=16):
        super(GaussianBlur, self).__init__()
        kernel = [[[[1, 0, -1],
                  [1, 0, -1],
                  [1, 0, -1]]],
                  [[[-1, 0, 1],
                   [-1, 0, 1],
                   [-1, 0, 1]]],
                  [[[1, 1, 1],
                   [0, 0, 0],
                   [-1, -1, -1]]],
                  [[[-1, -1, -1],
                   [0, 0, 0],
                   [1, 1, 1]]]]
        kernel = torch.FloatTensor(kernel).repeat(channels,1,1,1)
        self.weight = nn.Parameter(data=kernel, requires_grad=False)
#        self.B=nn.BatchNorm2d(channels)     
        self.net=nn.Sequential(
                nn.ReLU(),
                nn.PixelShuffle(2),
                nn.AdaptiveAvgPool2d(1)
                )
#        self.Ada=nn.AdaptiveAvgPool2d((1,1))
        self.fc=nn.Sequential(
                nn.Linear(channels,channels//reduction,bias=False),
                nn.ReLU(inplace=True),
                nn.Linear(channels//reduction,channels,bias=False),
                nn.Sigmoid()
                ) 
    def forward(self, x):
        B,C,_,_=x.size()
        out = F.conv2d(x, self.weight , bias=None, padding=1, groups=C)
        out=self.net(out).view(B,C)
#        Ada=self.Ada(x)
#        out=torch.matmul(out,Ada)
#        out=out.expand(x.shape)
#        out=torch.matmul(out,x)
        out=self.fc(out).view(B,C,1,1)
        return x * out.expand_as(x)
class ResidualBlock(nn.Module):
    def __init__(self, in_channels, out_channels, k=3, p=1):
        super(ResidualBlock, self).__init__()
        self.net = nn.Sequential(
			nn.Conv2d(in_channels, out_channels, kernel_size=k, padding=p),
		   	nn.BatchNorm2d(out_channels),
            GaussianBlur(out_channels),
			nn.BatchNorm2d(out_channels),
			nn.PReLU(),
        	
        	nn.Conv2d(out_channels, out_channels, kernel_size=k, padding=p),
			nn.BatchNorm2d(out_channels),
            GaussianBlur(out_channels),
        	nn.BatchNorm2d(out_channels)
        )
     #   self.EA=GaussianBlur(out_channels)

    def forward(self, x):
  #      x=self.EA(x)#通道放大
        return x + self.net(x)

class UpsampleBLock(nn.Module):
	def __init__(self, in_channels, scaleFactor, k=3, p=1):
		super(UpsampleBLock, self).__init__()
		self.net = nn.Sequential(
			nn.Conv2d(in_channels, in_channels * (scaleFactor ** 2), kernel_size=k, padding=p),
#            nn.BatchNorm2d(in_channels* (scaleFactor ** 2)),
            nn.PReLU(),
            nn.Conv2d(in_channels * (scaleFactor ** 2), in_channels * (scaleFactor ** 2), kernel_size=1, padding=0),
#            nn.BatchNorm2d(in_channels* (scaleFactor ** 2)),
#            nn.PReLU(),
#            nn.Conv2d(in_channels * (scaleFactor ** 2), in_channels * (scaleFactor ** 2), kernel_size=1, padding=0),
			nn.PixelShuffle(scaleFactor),
			nn.PReLU()
		)	
	def forward(self, x):
		return self.net(x)
        
class Generator_EAGAN(nn.Module):
    def __init__(self, n_residual=8, channels=64):
        super(Generator_EAGAN, self).__init__()
        self.n_residual = n_residual
        self.conv1 = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=9, padding=4),
            nn.PReLU()
        )
        
        for i in range(n_residual):
            self.add_module('residual' + str(i+1), ResidualBlock(64, 64))
        
        self.conv2 = nn.Sequential(
            nn.Conv2d(64, 64, kernel_size=3, padding=1),
            nn.PReLU()
        )
        
        self.upsample = nn.Sequential(
#            nn.Conv2d(64, 64, kernel_size=1, padding=0),
        	UpsampleBLock(64, 2),
        	UpsampleBLock(64, 2),
        	nn.Conv2d(64, 3, kernel_size=9, padding=4)
        )

    def forward(self, x):
        #print ('G input size :' + str(x.size()))
        y = self.conv1(x)
        cache = y.clone()#复制一个张量副本
        
        for i in range(self.n_residual):
            y = self.__getattr__('residual' + str(i+1))(y)
            
        y = self.conv2(y)
        y = self.upsample(y + cache)
        #print ('G output size :' + str(y.size()))
        return (torch.tanh(y) + 1.0) / 2.0
    
class Discriminator(nn.Module):
	def __init__(self, l=0.2):
		super(Discriminator, self).__init__()
		self.net = nn.Sequential(
			nn.Conv2d(3, 64, kernel_size=3, padding=1),
			nn.LeakyReLU(l),

			nn.Conv2d(64, 64, kernel_size=3, stride=2, padding=1),
			nn.BatchNorm2d(64),
			nn.LeakyReLU(l),

			nn.Conv2d(64, 128, kernel_size=3, padding=1),       
			nn.BatchNorm2d(128),
			nn.LeakyReLU(l),

			nn.Conv2d(128, 128, kernel_size=3, stride=2, padding=1),
        	nn.BatchNorm2d(128),
			nn.LeakyReLU(l),

			nn.Conv2d(128, 256, kernel_size=3, padding=1),
        	nn.BatchNorm2d(256),
			nn.LeakyReLU(l),

			nn.Conv2d(256, 256, kernel_size=3, stride=2, padding=1),
        	nn.BatchNorm2d(512),
			nn.LeakyReLU(l),

			nn.Conv2d(256, 512, kernel_size=3, padding=1),
        	nn.BatchNorm2d(512),
			nn.LeakyReLU(l),

			nn.Conv2d(512, 512, kernel_size=3, stride=2, padding=1),
        	nn.BatchNorm2d(512),
			nn.LeakyReLU(l),

			nn.AdaptiveAvgPool2d(1),
			nn.Conv2d(512, 1024, kernel_size=1),
			nn.LeakyReLU(l),
			nn.Conv2d(1024, 1, kernel_size=1)
		)

	def forward(self, x): 
		#print ('D input size :' +  str(x.size()))
		y = self.net(x)
		#print ('D output size :' +  str(y.size()))
		si = torch.sigmoid(y).view(y.size()[0])
		#print ('D output : ' + str(si))
		return si
		
class Discriminator_WGAN(nn.Module):
	def __init__(self, l=0.2):
		super(Discriminator_WGAN, self).__init__()
		self.net = nn.Sequential(
			nn.Conv2d(3, 64, kernel_size=3, padding=1),
			nn.LeakyReLU(l),

			nn.Conv2d(64, 64, kernel_size=3, stride=2, padding=1),
			nn.LeakyReLU(l),

			nn.Conv2d(64, 128, kernel_size=3, padding=1),
			nn.LeakyReLU(l),

			nn.Conv2d(128, 128, kernel_size=3, stride=2, padding=1),
			nn.LeakyReLU(l),

			nn.Conv2d(128, 256, kernel_size=3, padding=1),
			nn.LeakyReLU(l),

			nn.Conv2d(256, 256, kernel_size=3, stride=2, padding=1),
			nn.LeakyReLU(l),

			nn.Conv2d(256, 512, kernel_size=3, padding=1),
			nn.LeakyReLU(l),

			nn.Conv2d(512, 512, kernel_size=3, stride=2, padding=1),
			nn.LeakyReLU(l),

			nn.AdaptiveAvgPool2d(1),
			nn.Conv2d(512, 1024, kernel_size=1),
			nn.LeakyReLU(l),
			nn.Conv2d(1024, 1, kernel_size=1)
		)

	def forward(self, x): 
		#print ('D input size :' +  str(x.size()))
		y = self.net(x)
		#print ('D output size :' +  str(y.size()))
		return y.view(y.size()[0])

def compute_gradient_penalty(D, real_samples, fake_samples):
	alpha = torch.randn(real_samples.size(0), 1, 1, 1)
	if torch.cuda.is_available():
		alpha = alpha.cuda()
		
	interpolates = (alpha * real_samples + ((1 - alpha) * fake_samples)).requires_grad_(True)
	d_interpolates = D(interpolates)
	fake = torch.ones(d_interpolates.size())
	if torch.cuda.is_available():
		fake = fake.cuda()
		
	gradients = torch.autograd.grad(
        outputs=d_interpolates,
        inputs=interpolates,
        grad_outputs=fake,
        create_graph=True,
        retain_graph=True,
        only_inputs=True,
    )[0]
	gradients = gradients.view(gradients.size(0), -1)
	gradient_penalty = ((gradients.norm(2, dim=1) - 1) ** 2).mean()
	return gradient_penalty		


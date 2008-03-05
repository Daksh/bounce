/*
    Copyright 2008 by Wade Brainerd.  
    This file is part of 3D Pong.

    3D Pong is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    3D Pong is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with 3D Pong.  If not, see <http://www.gnu.org/licenses/>.
*/
#include "pongc.h"

#include <algorithm>

float frac(float x)
{
	return x-int(x);
}

void draw_point_2x(GdkImage* img, int x, int y, uint16_t c)
{
	c >>= 3;
	unsigned short* pixels = (unsigned short*)img->mem;
	int pitch = img->bpl/sizeof(unsigned short);
	int ofs = pitch*y*2+x*2;
	uint16_t pix = c | c<<6 | c<<11;
	pixels[ofs] = pix;
	pixels[ofs+1] = pix;
	pixels[ofs+pitch] = pix;
	pixels[ofs+pitch+1] = pix;
}

void clear_image(GdkImage* img)
{
	unsigned short* pixels = (unsigned short*)img->mem;
	int pitch = img->bpl/sizeof(unsigned short);
	for (int y = 0; y < img->height; y++)
		memset(pixels + pitch*y, 0, img->bpl);
}

void draw_line_2x(GdkImage* img, int x0, int y0, int x1, int y1, int color)
{
	// Convert to scaled coordinates.
	x0 >>= 1;
	x1 >>= 1;
	y0 >>= 1;
	y1 >>= 1;

	// Make sure the line runs top to bottom.
	if (y0 > y1) 
	{
		int ty = y0; y0 = y1; y1 = ty;
		int tx = x0; x0 = x1; x1 = tx;
	}

	// Draw the initial pixel, which is always exactly intersected by the line and so needs no weighting.
	draw_point_2x(img, x0, y0, color);
	
	int dx = x1 - x0;
	int xdir;
	if (dx >= 0)
		xdir = 1;
	else 
	{
		xdir = -1;
		dx = -dx; // make dx positive.
	}
	
	int dy = y1 - y0;
	if (dy == 0) // Horizontal line
	{
		while (dx-- != 0) 
		{
			x0 += xdir;
			draw_point_2x(img, x0, y0, color);
		}
	}
	else if (dx == 0) // Vertical line
	{
		do 
		{
			y0++;
			draw_point_2x(img, x0, y0, color);
		} while (--dy != 0);
	}
	else if (dx == dy) // Diagonal line
	{
		do 
		{
			x0 += xdir;
			y0++;
			draw_point_2x(img, x0, y0, color);
		} while (--dy != 0);
	}
	else // Line is not horizontal, diagonal, or vertical.
	{
		// Initialize the line error accumulator to 0 
		uint16_t ErrorAcc = 0;  
		
		// # of bits by which to shift ErrorAcc to get intensity level 
		uint16_t IntensityShift = 16 - 8;
		
		// Mask used to flip all bits in an intensity weighting, producing the result (1 - intensity weighting) 
		uint16_t WeightingComplementMask = 256 - 1;
		
		// Is this an X-major or Y-major line?
		if (dy > dx) 
		{
			// Y-major line; calculate 16-bit fixed-point fractional part of a pixel that X advances each time Y advances 
			// 1 pixel, truncating the result so that we won't overrun the endpoint along the X axis
			uint16_t ErrorAdj = ((unsigned long) dx << 16) / (unsigned long) dy;
			// Draw all pixels other than the first and last
			while (--dy) 
			{
				uint16_t ErrorAccTemp = ErrorAcc;   /* remember currrent accumulated error */
				ErrorAcc += ErrorAdj;      /* calculate error for next pixel */
				if (ErrorAcc <= ErrorAccTemp) 
				{
					// The error accumulator turned over, so advance the X coord
					x0 += xdir;
				}
				y0++; // Y-major, so always advance Y
				// The IntensityBits most significant bits of ErrorAcc give us the intensity weighting for this pixel, and the 
				// complement of the weighting for the paired pixel
				uint16_t Weighting = ErrorAcc >> IntensityShift;
				//draw_point_2x(img, x0, y0, (color * Weighting) >> 8);
				//draw_point_2x(img, x0 + xdir, y0, (color * (Weighting ^ WeightingComplementMask)) >> 8);
				draw_point_2x(img, x0, y0, color);
			}
			// Draw the final pixel, which is always exactly intersected by the line and so needs no weighting
			draw_point_2x(img, x1, y1, color);
		}
		else
		{
			// It's an X-major line; calculate 16-bit fixed-point fractional part of a pixel that Y advances each time X 
			// advances 1 pixel, truncating the result to avoid overrunning the endpoint along the X axis
			uint16_t ErrorAdj = ((unsigned long) dy << 16) / (unsigned long) dx;
			// Draw all pixels other than the first and last
			while (--dx) 
			{
				uint16_t ErrorAccTemp = ErrorAcc;   // remember currrent accumulated error
				ErrorAcc += ErrorAdj;      // calculate error for next pixel
				if (ErrorAcc <= ErrorAccTemp) 
				{
					// The error accumulator turned over, so advance the Y coord
					y0++;
				}
				x0 += xdir; // X-major, so always advance X 
				// The IntensityBits most significant bits of ErrorAcc give us the intensity weighting for this pixel, and the 
				// complement of the weighting for the paired pixel
				uint16_t Weighting = ErrorAcc >> IntensityShift;
				//draw_point_2x(img, x0, y0, (color * Weighting) >> 8);
				//draw_point_2x(img, x0, y0 + 1, (color * (Weighting ^ WeightingComplementMask)) >> 8);
				draw_point_2x(img, x0, y0, color);
			}
			// Draw the final pixel, which is always exactly intersected by the line and so needs no weighting
			draw_point_2x(img, x1, y1, color);
		}
	}
}


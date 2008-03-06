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
#ifndef _PONGC_H_
#define _PONGC_H_

#include <python2.5/Python.h>

// todo- Include the real GTK headers when installed.
#include "gtk_types.h"

void clear_image(GdkImage* img);

void draw_line_2x(GdkImage* img, int x0, int y0, int x1, int y1, int color);

void draw_ellipse_2x(GdkImage* img, int x, int y, int rx, int ry, int color);
void fill_ellipse_2x(GdkImage* img, int x, int y, int rx, int ry, int color);

#endif


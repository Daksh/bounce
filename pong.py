#!/usr/bin/env python
"""3DPong - 3D action game by Wade Brainerd."""

import logging, os, time, math, threading, random
from gettext import gettext as _

import gobject, pygtk, gtk, pango, cairo
gobject.threads_init()  

from sugar.activity import activity
from sugar.graphics import *

log = logging.getLogger('3dpong')
log.setLevel(logging.DEBUG)
logging.basicConfig()
gtk.add_log_handlers()

def clamp(a, b, c):
    if (a<b): return b
    elif (a>c): return c
    else: return a

def to_fixed(a):
    return int(a * 256)

def from_fixed(a):
    return a >> 8

def fixed_mul(a, b):
    return (a * b) >> 8

class Vector:
    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z

zerovec = Vector(0, 0, 0)

class Color:
    def __init__(self, r=255, g=255, b=255):
        self.r = r
        self.g = g
        self.b = b

class Rect:
    def __init__(self):
        self.top = 0
        self.left = 0
        self.right = 0
        self.bottom = 0

stage_descs = [
    { 'Name': _('normal'), 'AISpeed': 1, 'AIRecenter': 1, 'StageDepth': 160, 'StageGravity': 0, 'StageCrossGravity': 0, 'BallSize': 1, 'BallSpeed': 3, 'PaddleWidth': 20, 'PaddleHeight': 20 },
    { 'Name': _('bounce'), 'AISpeed': 2, 'AIRecenter': 1, 'StageDepth': 160, 'StageGravity': 1, 'StageCrossGravity': 0, 'BallSize': 1, 'BallSpeed': 3, 'PaddleWidth': 20, 'PaddleHeight': 20 },
    { 'Name': _('wide'),   'AISpeed': 4, 'AIRecenter': 1, 'StageDepth': 160, 'StageGravity': 1, 'StageCrossGravity': 0, 'BallSize': 1, 'BallSpeed': 4, 'PaddleWidth': 100, 'PaddleHeight': 15 },
    { 'Name': _('deep'),   'AISpeed': 5, 'AIRecenter': 0, 'StageDepth': 500, 'StageGravity': 0, 'StageCrossGravity': 0, 'BallSize': 1, 'BallSpeed': 10, 'PaddleWidth': 25, 'PaddleHeight': 25 },
    { 'Name': _('rotate'), 'AISpeed': 5, 'AIRecenter': 1, 'StageDepth': 160, 'StageGravity': 0, 'StageCrossGravity': 1, 'BallSize': 1, 'BallSpeed': 5, 'PaddleWidth': 25, 'PaddleHeight': 20 },
]


# Virtual screen dimensions
# This game was ported from a Palm OS app, and it would be difficult to change all the internal calculations to a new resolution. 
actual_screen_width = 1200
actual_screen_height = 825

# Game constants
viewport_scale = to_fixed(100)
time_res = 32

def project_x(x, y, z):
    return (to_fixed(50) + ( x - to_fixed(50) ) * viewport_scale / ( z + viewport_scale )) * actual_screen_width/100 / 256

def project_y(x, y, z):
    return (to_fixed(50) + ( y - to_fixed(50) ) * viewport_scale / ( z + viewport_scale )) * actual_screen_height/100 / 256

PRIM_LINE = 0
PRIM_FILL = 1

curprim = PRIM_LINE

def flush_prim ():
    global curprim
    if curprim == PRIM_LINE:
        game.cairo.stroke()
    else:
        game.cairo.fill()

def begin_prim (prim):
    global curprim
    if prim != curprim:
        flush_prim()
        curprim = prim

def set_color (color):
    flush_prim()
    game.cairo.set_source_rgb(color.r/255.0, color.g/255.0, color.b/255.0)

def line3d(x1, y1, z1, x2, y2, z2):
    game.cairo.move_to(project_x( x1, y1, z1 ), project_y( x1, y1, z1 ))
    game.cairo.line_to(project_x( x2, y2, z2 ), project_y( x2, y2, z2 ))

def rect3d(rect, depth):
    x1 = project_x( rect.left, rect.top, depth ) + 1
    y1 = project_y( rect.left, rect.top, depth ) + 1
    x2 = project_x( rect.right, rect.bottom, depth ) - 1
    y2 = project_y( rect.right, rect.bottom, depth ) - 1

    game.cairo.move_to(x1, y1)
    game.cairo.line_to(x2, y1)
    game.cairo.line_to(x2, y2)
    game.cairo.line_to(x1, y2)
    game.cairo.line_to(x1, y1)

def circle3d(x, y, z, radius):
    r = project_x(x+radius, y, z)-project_x(x, y, z)
    if r < 1: return

    x = project_x( x, y, z )
    y = project_y( x, y, z )

    game.cairo.move_to(x+r, y)
    game.cairo.arc(x, y, r, 0, 2*math.pi)

def draw_text (text, x, y, size):
    game.cairo.set_font_size(size)
    x_bearing, y_bearing, width, height = game.cairo.text_extents(text)[:4]

    if x == -1: x = actual_screen_width/2
    if y == -1: y = actual_screen_height/2

    game.cairo.move_to(x - width/2 - x_bearing, y - height/2 - y_bearing)
    game.cairo.show_text(text)

class Ball:
    def __init__(self):
        self.lastpos = Vector()
        self.lastvel = Vector()
        self.pos = Vector()
        self.vel = Vector()
    
    def draw (self, stage):
        # Draw the ball.
        begin_prim(PRIM_FILL)
        circle3d(self.pos.x, self.pos.y, self.pos.z, stage.ballsize)
    
        # Draw the shadow.
        #DrawEllipse3D(Ball.pos.x, Stage.window.bottom, Ball.pos.z, game.stage.ballsize*2, game.stage.ballsize, (64, 64, 64))

    def setup (self, speed):
        self.pos = Vector(to_fixed(50), to_fixed(25), game.stage.depth/2)
        self.vel = Vector(to_fixed(2), to_fixed(2), speed)

    # 0 if nobody scored, 1 if Paddle1 scored, 2 if Paddle2 scored.
    def update (self, paddle1, paddle2, stage):
        # Ball collisions are handled very accurately, as this is the basis of the game.
        # All times are in 1sec/time_res units.
        # 1. Loop through all the surfaces and finds the first one the ball will collide with
        # in this animation frame (if any). 
        # 2. Update the Ball velocity based on the collision, and advance the current time to 
        # the exact time of the collision.
        # 3. Goto step 1, until no collisions remain in the current animation frame.
    
        time_left = time_res                  # Time remaining in this animation frame.
        first_collision_time = 0              # -1 means no collision found.
        first_collision_vel = Vector()    # New ball velocity from first collision.
        first_collision_type = 0              # 0 for normal collision (wall), otherwise the scorezone number hit. 
    
        self.lastpos.x = self.pos.x
        self.lastpos.y = self.pos.y
        self.lastpos.z = self.pos.z
        self.lastvel.x = self.vel.x
        self.lastvel.y = self.vel.y
        self.lastvel.z = self.vel.z
    
        next_ball_pos = Vector()          # Hypothetical ball position assuming no collision.
        cur_time = 0                            # cur_time of current collision.
        
        collision_type = 0                   # Stored return value.
    
        iterations = 0
    
        while True:
            iterations = iterations+1
            if ( iterations > 5 ):
                break
    
            # Calculate new next ball position.
            next_ball_pos.x = self.pos.x + (self.vel.x * time_left) / time_res
            next_ball_pos.y = self.pos.y + (self.vel.y * time_left) / time_res
            next_ball_pos.z = self.pos.z + (self.vel.z * time_left) / time_res
    
            # Reset first_collision_cur_time.     
            first_collision_cur_time = -1
    
            # Check stage walls.  First checks to see if the boundary was crossed, if so then calculates cur_time, etc.
            if ( next_ball_pos.x - game.stage.ballsize <= 0 ): # Left wall
                cur_time = ( self.pos.x - game.stage.ballsize ) * time_res / -self.vel.x # negative Vx is to account for left wall facing.
                if ( first_collision_cur_time == -1 or cur_time < first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = -self.vel.x
                    first_collision_vel.y = self.vel.y
                    first_collision_vel.z = self.vel.z
                    first_collision_type = 5
            if ( next_ball_pos.x + game.stage.ballsize >= stage.window.right ): # Right wall
                cur_time = ( stage.window.right - ( self.pos.x + game.stage.ballsize ) ) * time_res / self.vel.x
                if ( first_collision_cur_time == -1 or cur_time < first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = -self.vel.x
                    first_collision_vel.y = self.vel.y
                    first_collision_vel.z = self.vel.z
                    first_collision_type = 5
            if ( next_ball_pos.y - game.stage.ballsize <= 0 and self.vel.y != 0): # Top wall
                cur_time = ( self.pos.y - game.stage.ballsize ) * time_res / -self.vel.y
                if ( first_collision_cur_time == -1 or cur_time < first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = self.vel.x
                    first_collision_vel.y = -self.vel.y
                    first_collision_vel.z = self.vel.z
                    first_collision_type = 5
            if ( next_ball_pos.y + game.stage.ballsize >= stage.window.bottom  and self.vel.y != 0): # Bottom wall
                cur_time = ( stage.window.bottom - ( self.pos.y + game.stage.ballsize ) ) * time_res / self.vel.y
                if ( first_collision_cur_time == -1 or cur_time < first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = self.vel.x
                    first_collision_vel.y = -self.vel.y
                    first_collision_vel.z = self.vel.z
                    first_collision_type = 5
            if ( next_ball_pos.z <= 0 ): # Front wall
                cur_time = self.pos.z * time_res / -self.vel.z
                if ( first_collision_cur_time == -1 or cur_time < first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = self.vel.x #(random.randint(0, 3))-1 * game.stage.ballspeed
                    first_collision_vel.y = self.vel.y #(random.randint(0, 3))-1 * game.stage.ballspeed
                    first_collision_vel.z = game.stage.ballspeed
                    first_collision_type = 2
            if ( next_ball_pos.z >= stage.depth ): # Back wall
                cur_time = ( stage.depth - self.pos.z ) * time_res / self.vel.z
                if ( first_collision_cur_time == -1 or cur_time < first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = self.vel.x #(random.randint(0, 3))-1 * game.stage.ballspeed
                    first_collision_vel.y = self.vel.y #(random.randint(0, 3))-1 * game.stage.ballspeed
                    first_collision_vel.z = -game.stage.ballspeed
                    first_collision_type = 1
            # Paddle collision.  Paddle collisions are inaccurate, in that it doesn't take into account the velocity of 
            # the ball in its 2D check, it uses the original 2D position.
            if (        self.vel.z < 0 
                    and ( self.pos.z >= paddle1.pos.z or self.pos.z >= paddle1.pos.z - math.fabs(paddle1.delta.z) ) 
                    and ( next_ball_pos.z <= paddle1.pos.z or next_ball_pos.z <= paddle1.pos.z + math.fabs(paddle1.delta.z) )
                    and self.pos.x >= paddle1.pos.x - paddle1.halfwidth
                    and self.pos.x <= paddle1.pos.x + paddle1.halfwidth 
                    and self.pos.y >= paddle1.pos.y - paddle1.halfheight
                    and self.pos.y <= paddle1.pos.y + paddle1.halfheight ):
                cur_time = ( self.pos.z - paddle1.pos.z ) * time_res / -self.vel.z
                if ( first_collision_cur_time == -1 or cur_time <= first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = self.vel.x
                    first_collision_vel.y = self.vel.y
                    first_collision_vel.z = -self.vel.z
    
                    # If paddle is moving forward, bounce the ball off.
                    if ( paddle1.delta.z > 0 ):
                        first_collision_vel.z += 4*246
    
                        # Apply some pong like angling based on where it hits the paddle.
                        if ( next_ball_pos.x - paddle1.pos.x > 20 ):
                            first_collision_vel.x += 2*256
                        if ( next_ball_pos.x - paddle1.pos.x < -20 ):
                            first_collision_vel.x -= 2*256
    
                        if ( next_ball_pos.y - paddle1.pos.y > 15 ):
                            first_collision_vel.y += 2*256
                        if ( next_ball_pos.y - paddle1.pos.y < -15 ):
                            first_collision_vel.y -= 2*256
                    # Likewise if paddle is moving backwards, cushion it.
                    if ( paddle1.delta.z < 0 ):
                        first_collision_vel.z -= 2*256
                    
                    first_collision_type = 3
            # Computer paddle.
            if (        self.vel.z > 0 
                    and ( self.pos.z <= paddle2.pos.z ) 
                    and ( next_ball_pos.z >= paddle2.pos.z )
                    and self.pos.x >= paddle2.pos.x - paddle2.halfwidth
                    and self.pos.x <= paddle2.pos.x + paddle2.halfwidth 
                    and self.pos.y >= paddle2.pos.y - paddle2.halfheight
                    and self.pos.y <= paddle2.pos.y + paddle2.halfheight ): # Paddle 2
                cur_time = ( paddle2.pos.z - self.pos.z ) * time_res / self.vel.z
                if ( first_collision_cur_time == -1 or cur_time <= first_collision_cur_time ):
                    # Set new first collision.
                    first_collision_cur_time = cur_time
                    first_collision_vel.x = self.vel.x
                    first_collision_vel.y = self.vel.y
                    first_collision_vel.z = -self.vel.z + ( paddle1.delta.z > 0 ) * 2*256 + ( paddle1.delta.z < 0 ) * 2*256
                    first_collision_type = 4
    
            # Advance the ball to the point of the first collision.
            if ( first_collision_cur_time != -1 ):
                self.pos.x += self.vel.x * first_collision_cur_time / time_res
                self.pos.y += self.vel.y * first_collision_cur_time / time_res
                self.pos.z += self.vel.z * first_collision_cur_time / time_res
                self.vel.x = first_collision_vel.x
                self.vel.y = first_collision_vel.y
                self.vel.z = first_collision_vel.z
                
                time_left -= first_collision_cur_time
                collision_type = first_collision_type
            if ( not (first_collision_cur_time != -1 and time_left > 0) ):
                break
    
        # If there's time left in the frame w/o collision, finish it up.    
        if time_left > 0:
            self.pos.x += self.vel.x * time_left / time_res
            self.pos.y += self.vel.y * time_left / time_res
            self.pos.z += self.vel.z * time_left / time_res
    
        # Apply gravity.
        self.vel.y += game.stage.gravity
        if ( self.pos.y + game.stage.ballsize + 20 > stage.window.bottom and math.fabs(self.vel.y) == 0 ):
            self.vel.y -= 6
        self.vel.x += game.stage.crossgravity
    
        # Calculate scores if any collisions with the back wall happened.
        if collision_type == 1:
            paddle1.score += 1
        elif collision_type == 2:
            paddle2.score += 1  
        #elif collision_type == 3:
        #    game.Player1PaddleWav.play()    
        #elif collision_type == 4:
        #    game.Player2PaddleWav.play()    
        #elif collision_type == 5:
        #    game.WallWav.play() 

        return collision_type

class Paddle:
    def __init__(self):
        # Center of the paddle
        self.pos = Vector()
        
        # Physics stuff
        self.delta = Vector() # Amount moved since last update for spin calc.
        self.halfwidth = 0
        self.halfheight = 0

        # Stuff for moving the paddle forward.
        self.targetz = 0
        self.defaultz = 0
        self.forwardz = 0

        # AI stuff
        self.vel = Vector()
        self.speed = 0

        # Game stuff
        self.score = 0

    def draw (self, stage):
        begin_prim(PRIM_LINE)
    
        r = Rect()
        r.left = self.pos.x - self.halfwidth 
        r.right = self.pos.x + self.halfwidth    
        r.top = self.pos.y - self.halfheight 
        r.bottom = self.pos.y + self.halfheight  
        
        rect3d( r, self.pos.z )
    
        x = r.left + ( ( r.right - r.left ) / 2 )
        line3d( x, r.bottom, self.pos.z, x, stage.window.bottom, self.pos.z )

    def clip_position (self):
        self.pos.x = max(self.pos.x, self.halfwidth)
        self.pos.y = max(self.pos.y, self.halfheight)
        self.pos.x = min(self.pos.x, game.stage.window.right - self.halfwidth)
        self.pos.y = min(self.pos.y, game.stage.window.bottom - self.halfheight)

    def setup_player(self, w, h):
        self.halfwidth = w
        self.halfheight = h

        self.delta = zerovec
        self.pos = Vector(to_fixed(25), to_fixed(50), to_fixed(10))
        self.clip_position()

        self.defaultz = self.pos.z
        self.targetz = self.pos.z
        self.forwardz = to_fixed(40)

        self.score = 0

    def update_player (self, stage):
        """Check paddle inputs and apply to paddle."""
        lastpos = Vector()
        lastpos.x = self.pos.x
        lastpos.y = self.pos.y
        lastpos.z = self.pos.z
    
        penx = game.mousex*100/actual_screen_width
        peny = game.mousey*100/actual_screen_height
        pendown = 1
    
        if ( game.mousedown ):
            self.targetz = self.forwardz
        else:
            self.targetz = self.defaultz
    
        # Snaps forward, eases back.
        if ( self.pos.z < self.targetz ):
            if ( self.delta.z < to_fixed(4) ):
                self.delta.z = to_fixed(6)
            self.pos.z += self.delta.z + to_fixed(2)
            if ( self.pos.z > self.targetz ):
                self.pos.z = self.targetz
    
        if ( self.pos.z > self.targetz ):
            self.pos.z += ( self.targetz - self.pos.z ) / 4
    
        # Get the 2d position from the pen.
        if ( pendown ): 
            self.pos.x = to_fixed(penx)
            self.pos.y = to_fixed(peny)
            self.clip_position()
    
        self.delta.x = self.pos.x - lastpos.x
        self.delta.y = self.pos.y - lastpos.y
        self.delta.z = self.pos.z - lastpos.z

    def setup_ai (self, w, h):
        self.score = 0

        self.halfwidth = w
        self.halfheight = h

        self.pos = Vector(to_fixed(75), to_fixed(50), game.stage.depth - to_fixed(10))

        self.defaultz = self.pos.z
        self.targetz = self.pos.z
        self.forwardz = game.stage.depth - 40*256

        self.delta = zerovec
        self.vel = zerovec

        self.clip_position()
    
    def update_ai (self, ball, stage):
        """Compute AI and move paddle."""
        # Only move when the ball is coming back, that way it appears to react to the players hit.
        # Actually, start moving just before the player hits it.
        if ( ball.vel.z > 0 or ball.vel.z < 0 and ball.pos.z < to_fixed(30)) :
            # Acceleration towards the ball.
            if ( math.fabs( ( self.pos.x - ball.pos.x ) ) > to_fixed(5) ):
                if ( self.pos.x < ball.pos.x ):
                    self.vel.x += to_fixed(4)
                if ( self.pos.x > ball.pos.x ):
                    self.vel.x -= to_fixed(4)
                
            if ( math.fabs( ( self.pos.y - ball.pos.y ) ) > to_fixed(5) ):
                if ( self.pos.y < ball.pos.y ):
                    self.vel.y += to_fixed(4)
                if ( self.pos.y > ball.pos.y ): 
                    self.vel.y -= to_fixed(4)
            
            # Speed clamping
            self.vel.x = clamp( self.vel.x, -game.ai.speed, game.ai.speed )
            self.vel.y = clamp( self.vel.y, -game.ai.speed, game.ai.speed )
        elif ( ball.pos.z < game.stage.depth/2 ):
            self.vel.x = 0
            self.vel.y = 0
            # Drift towards the center.
            if ( game.ai.recenter ):
                self.pos.x += ( to_fixed(50) - self.pos.x ) / 4
                self.pos.y += ( to_fixed(50) - self.pos.y ) / 4
                
        # Friction
        if ( self.vel.x > 0 ):
            self.vel.x -= 1
        if ( self.vel.x < 0 ):
            self.vel.x += 1
            
        if ( self.vel.y > 0 ):
            self.vel.y -= 1
        if ( self.vel.y < 0 ):
            self.vel.y += 1
            
        self.pos.x += self.vel.x
        self.pos.y += self.vel.y
        self.clip_position()

class Stage:
    def __init__(self):
        # How long the stage is from near side to far side.
        self.depth = 0
        self.window = Rect()

        self.gravity = 0
        self.crossgravity = 0
        self.ballspeed = 0
        self.ballsize = 0

    def draw (self):
        window = self.window
    
        begin_prim(PRIM_LINE)
        v = 255*game.brightness/100.0
        set_color(Color(v,v,v))
    
        # Near and far rectangles   
        rect3d( window, 0 )
        rect3d( window, self.depth )
    
        # Diagonals
        line3d( window.left, window.top, 1, window.left, window.top, self.depth )
        line3d( window.left, window.bottom, 1, window.left, window.bottom, self.depth )
        line3d( window.right, window.top, 1, window.right, window.top, self.depth )
        line3d( window.right, window.bottom, 1, window.right, window.bottom, self.depth )

        # Wall grids.
        set_color(Color(64, 64, 64))
    
        i = 1
        while i < 5:
            x = i*(window.right-window.left)/5
            i += 1
            line3d(x, window.top, 1, x, window.top, self.depth)
            line3d(x, window.bottom, 1, x, window.bottom, self.depth)
    
        i = 1
        while i < 5:
            x = i*(window.bottom-window.top)/5
            i += 1
            line3d(window.left, x, 1, window.left, x, self.depth)
            line3d(window.right, x, 1, window.right, x, self.depth)
            
        i = 1
        while i < 5:
            x = i*(self.depth)/5
            i += 1
            line3d(window.left, window.top, x, window.right, window.top, x)
            line3d(window.left, window.bottom, x, window.right, window.bottom, x)
            line3d(window.left, window.top, x, window.left, window.bottom, x)
            line3d(window.right, window.top, x, window.right, window.bottom, x)

        v = 255*game.brightness/100.0
        set_color(Color(v,v,v))

    def setup(self, depth, grav, speed):
        self.gravity = grav
        self.ballspeed = speed
        self.depth = depth
        self.window.left = 0
        self.window.right = to_fixed(99)
        self.window.top = 0
        self.window.bottom = to_fixed(99)

class AI:
    def __init__(self):
        self.speed = 0
        self.recenter = False

class IntroSequence:
    def enter (self):
        self.timer0 = 0
        self.timer1 = 0

    def leave (self):
        pass

    def draw (self):
        if (self.timer1 == 1):
            game.draw()
        set_color(Color(self.timer0/100.0*255.0, self.timer0/100.0*255.0, self.timer0/100.0*255.0))
        draw_text(_("3 d   p o n g"), -1, -1, 100)

    def update (self):
        if (self.timer1 == 0):
            game.brightness = 0
            self.timer0 += 1
            if (self.timer0 >= 100):
                self.timer1 = 1
        elif (self.timer1 == 1):
            if (game.brightness < 100): game.brightness += 1
            self.timer0 -= 2
            if (self.timer0 <= 0):
                #game.IntroWav.play()
                game.set_sequence(BallReleaseSequence())

class NewStageSequence:
    def enter (self):
        self.timer0 = 0
        self.timer1 = 0

    def leave (self):
        pass

    def draw (self):
        game.draw()
        set_color(Color(self.timer0/100.0*255.0, self.timer0/100.0*255.0, self.timer0/100.0*255.0))
        draw_text(stage_descs[game.curlevel]['Name'], -1, -1, 100)

    def update (self):
        if (self.timer1 == 0):
            if (game.brightness > 0): game.brightness -= 5
            self.timer0 += 2
            if (self.timer0 >= 100):
                self.timer1 = 1
                game.next_level()
        elif (self.timer1 == 1):
            if (game.brightness < 100): game.brightness += 1
            self.timer0 -= 2
            if (self.timer0 <= 0):
                #game.IntroWav.play()
                game.set_sequence(BallReleaseSequence())

class BallReleaseSequence:
    def enter (self):
        self.timer0 = 0
        self.timer1 = 0

    def leave (self):
        pass

    def draw (self):
        game.draw()
        v = math.sin(3.14159*self.timer0/30.0)
        set_color(Color(v*255.0, v*255.0, v*255.0))
        draw_text(str(3-self.timer1), -1, -1, 20)

    def update (self):
        if (game.brightness < 100): game.brightness += 1
        self.timer0 += 1
        if (self.timer0 > 25):
            self.timer1 += 1
            self.timer0 = 0
        if (self.timer1 >= 3):
            game.set_sequence(PlaySequence())

class PlaySequence:
    def enter (self):
        self.timer0 = 0
        self.timer1 = 0
        self.endtimeout = 0

    def leave (self):
        pass

    def draw (self):
        game.draw()

    def update (self):
        # Process player input and AI.
        game.paddle1.update_player(game.stage)
        game.paddle2.update_ai(game.ball, game.stage)
        
        # Run the ball simulation.
        game.lastscore = game.ball.update(game.paddle1, game.paddle2, game.stage)
        if ( game.lastscore == 1 ):
            game.set_sequence(ScoreSequence())
        if ( game.lastscore == 2 ):
            game.set_sequence(ScoreSequence())
            
        # Check for end of game conditions.
        if ( game.paddle1.score == 5 or game.paddle2.score == 5 ):
            self.endtimeout += 1
        if ( self.endtimeout >= 5 ):
            stage_descs[game.curlevel]['PlayerScore'] = game.paddle1.score
            stage_descs[game.curlevel]['AIScore'] = game.paddle2.score
            if ( game.paddle2.score == 5 ):
                game.set_sequence(LoseSequence())
            if ( game.paddle1.score == 5 ):
                game.curlevel += 1
                if (game.curlevel == len(stage_descs)):
                    game.set_sequence(WinSequence())
                else:
                    game.set_sequence(NewStageSequence())

class ScoreSequence:
    def enter (self):
        self.step = 0
        self.num_steps = 20
        #game.scoreWav.play()

    def leave (self):
        #game.ball.vel = Vector(to_fixed(2), to_fixed(2), game.ball.vel.z)
        pass

    def draw (self):
        game.draw()

        ring_spacing = to_fixed(1)
        ring_speed = to_fixed(1)
        num_rings = 10

        b = 255*(1.0-float(self.step)/self.num_steps)
        set_color(Color(b,b,b))

        begin_prim(PRIM_LINE)
        circle3d(game.ball.lastpos.x+game.ball.lastvel.x*self.step/2, game.ball.lastpos.y+game.ball.lastvel.y*self.step/2, game.ball.lastpos.z+game.ball.lastvel.z*self.step/2, game.stage.ballsize)
        random.seed(12345678)
        for ring in range(0, num_rings):
            b = 255*(1.0-float(self.step)/self.num_steps)*(0.5+0.5*math.cos(math.pi*float(ring)/num_rings))
            circle3d(game.ball.lastpos.x+game.ball.lastvel.x*ring, game.ball.lastpos.y+game.ball.lastvel.y*ring, game.ball.lastpos.z+game.ball.lastvel.z*ring, (-ring+1)*ring_spacing + ring_speed*self.step)

    def update (self):
        self.step += 1
        if self.step >= self.num_steps:
            game.set_sequence(PlaySequence())

class LoseSequence:
    def enter (self):
        self.timer0 = 0
        self.timer1 = 0

    def leave (self):
        pass

    def draw (self):
        game.draw()
        set_color(Color(self.timer0/100.0, self.timer0/100.0, self.timer0/100.0))
        draw_text("; - {", -1, -1, 24)

    def update (self):
        if (self.timer1 == 0):
            if (game.brightness > 0): game.brightness -= 5
            self.timer0 += 2
            if (self.timer0 >= 100):
                self.timer1 = 1
                game.new_game()
        elif (self.timer1 == 1):
            self.timer0 -= 2
            if (self.timer0 <= 0):
                game.set_sequence(IntroSequence())
                self.timer0 = 0
                self.timer1 = 0

class WinSequence:
    def enter (self):
        self.timer0 = 0
        self.timer1 = 0

    def leave (self):
        pass

    def update (self):
        if (self.timer1 == 0):
            if (game.brightness > 0): game.brightness -= 5
            if (game.brightness <= 0):
                self.timer0 = 0
                self.timer1 = 1
            DrawGame()
        elif (self.timer1 == 1):
            self.timer0 += 1                
            if (self.timer0 >= 1000 or game.mousedown):
                self.timer1 = 2
                self.timer0 = len(stage_descs)*30
        elif (self.timer1 == 2):
            self.timer0 -= 1
            if (self.timer0 <= 0):
                game.new_game()
                game.set_sequence(IntroSequence())
                self.timer0 = 0
                self.timer1 = 0

    def draw (self):
        starty = 250
        total_score = 0
        for i in range(0, len(stage_descs)):
            v = clamp(255*self.timer0/60.0 - i*60, 0, 255)
            set_color(Color(v,v,v))

            player_score = stage_descs[i]['player_score']
            ai_score = stage_descs[i]['ai_score']
            diff_score = player_score - ai_score

            game.draw_score(250, starty + i*50, player_score, 0)
            draw_text('-', 475, starty + i*50, 20)
            game.draw_score(550, starty + i*50, ai_score, 1)
            draw_text('=', 775, starty + i*50, 20)
            game.draw_score(850, starty + i*50, diff_score, 0)

            draw_text(stage_descs[i]['Name'], 125, starty + i*50, 24)

            total_score += diff_score
    
        game.cairo.move_to(250, starty + len(stage_descs)*50)
        game.cairo.line_to(950, starty + len(stage_descs)*50)
        game.cairo.stroke()
        x = 250
        y = starty + (len(stage_descs)+1)*50
        for j in range(0, 5*len(stage_descs)):
            game.cairo.move_to(game.xpoints[0][0]*20-10+x, game.xpoints[0][1]*20-10+y)
            for p in game.xpoints:
                game.cairo.line_to(p[0]*20-10+x, p[1]*20-10+y)
            game.cairo.line_to(game.xpoints[0][0]*20-10+x, game.xpoints[0][1]*20-10+y)
            if j >= total_score:
                game.cairo.stroke()
            else:
                game.cairo.fill()
            x += 30
            if (x > 980):
                x = 250
                y += 50
    
        text = "; - |"
        if (total_score >= 5*len(stage_descs)):
            text = "; - D"
        elif (total_score >= 4*len(stage_descs)):
            text = "; - >"
        elif (total_score >= 3*len(stage_descs)):
            text = "; - )"
        elif (total_score >= 2*len(stage_descs)):
            text = "; - }"
        draw_text(text, -1, 150, 24)

class Game:
    def __init__(self):
        self.endtimeout = 0

        self.ai = AI()

        self.stage = Stage()
        self.ball = Ball()
        self.paddle1 = Paddle()
        self.paddle2 = Paddle()
        
        # Score variable from last frame, to see if we need to erase the scoring graphic.
        self.lastscore = 0
        
        # Current stage.
        self.curlevel = 0

        # Variables affecting the sequencer.
        self.sequence = IntroSequence()
        self.sequence.enter()
        self.brightness = 100
        
        # Current mouse state.
        self.mousex = 0
        self.mousey = 0
        self.mousedown = 0

        # The 'X' shape used as an icon.
        self.xpoints = [ (0,0), (0.3,0), (0.5,0.3), (0.7,0), (1,0), (0.7,0.5), (1,1), (0.7,1), (0.5,0.6), (0.3,1), (0,1), (0.3,0.5) ]

    def set_sequence (self, seq):
        self.sequence.leave()
        self.sequence = seq
        self.sequence.enter()

    def next_level(self):
        desc = stage_descs[self.curlevel]

        self.stage.name = desc['Name']

        self.stage.ballsize = to_fixed(desc['BallSize'])
        self.ball.setup(to_fixed(desc['BallSpeed']))

        self.stage.setup(to_fixed(desc['StageDepth']), to_fixed(desc['StageGravity']), to_fixed(desc['BallSpeed']))
        self.stage.crossgravity = to_fixed(desc['StageCrossGravity'])

        self.ai.speed = desc['AISpeed']*256
        self.ai.recenter = desc['AIRecenter']

        self.paddle1.setup_player(to_fixed(desc['PaddleWidth']), to_fixed(desc['PaddleHeight']))
        self.paddle2.setup_ai(to_fixed(desc['PaddleWidth']), to_fixed(desc['PaddleHeight']))
    
    def new_game(self):
        self.curlevel = 0
        self.next_level()
    
    def draw_score(self, x, y, score, player):
        for j in range(0, 5):
            if j < score:
                begin_prim(PRIM_FILL)
            else:
                begin_prim(PRIM_LINE)

            px = x + j*30
            py = y

            if player == 1:
                game.cairo.move_to(game.xpoints[0][0]*20-10+px, game.xpoints[0][1]*20-10+py)
                for p in game.xpoints:
                    game.cairo.line_to(p[0]*20-10+px, p[1]*20-10+py)
                game.cairo.line_to(game.xpoints[0][0]*20-10+px, game.xpoints[0][1]*20-10+py)
            elif player == 2:
                game.cairo.move_to(px + 10, py)
                game.cairo.arc(px, py, 10, 0, 2*math.pi)

    def draw(self):
        v = 255*self.brightness/100.0
        set_color(Color(v,v,v))

        self.stage.draw()
        self.paddle1.draw(self.stage)
        self.paddle2.draw(self.stage)
        self.ball.draw(self.stage)
    
        v = 255*self.brightness/100.0
        set_color(Color(v,v,v))
        self.draw_score(actual_screen_width*1/4-75, 30, self.paddle1.score, 1)
        self.draw_score(actual_screen_width*3/4-75, 30, self.paddle2.score, 2)
    
        #game.cairo.set_source_rgb(color[0]/255.0, color[1]/255.0, color[2]/255.0)
        #draw_text(stage_descs[game.curlevel]['Name'], -1, 30, 24)

# Global game instance.
game = Game()

class PongActivity(activity.Activity):

    def __init__ (self, handle):
        activity.Activity.__init__(self, handle)
        self.set_title(_("3dpong"))

        # Get activity size. 
        # todo- What we really need is the size of the canvasarea, not including the toolbox.
        self.width = gtk.gdk.screen_width()
        self.height = gtk.gdk.screen_height()

        # Build the toolbar.
        self.build_toolbar()

        # Set up the drawing window and context.
        self.build_drawarea()
        self.build_cairo()

        # Build the level editor.
        self.build_editor()

        # Turn off double buffering.
        self.set_double_buffered(False)
        self.drawarea.set_double_buffered(True)

        # Initialize the game.
        game.new_game()
        self.paused = False

        # Get the mainloop ready to run.
        gobject.timeout_add(50, self.mainloop)

        # Show everything.
        self.show_all()

    def build_drawarea (self):
        self.drawarea = gtk.Layout()
        self.drawarea.set_size_request(self.width, self.height)

        self.drawarea.connect('destroy', self.on_destroy)

        self.drawarea.add_events(gtk.gdk.POINTER_MOTION_MASK|gtk.gdk.BUTTON_PRESS_MASK|gtk.gdk.BUTTON_RELEASE_MASK)
        self.drawarea.connect('motion-notify-event', self.on_mouse)
        self.drawarea.connect('button-press-event', self.on_mouse)
        self.drawarea.connect('button-release-event', self.on_mouse)

        #self.drawarea.grab_add()
        self.cursor_visible = True

        self.set_canvas(self.drawarea)

    def build_cairo (self):
        game.cairosurf = cairo.ImageSurface(cairo.FORMAT_RGB24, self.width, self.height)
        game.cairo = cairo.Context(game.cairosurf)
        game.cairo.set_antialias(cairo.ANTIALIAS_NONE)
        #game.cairo.set_line_cap(cairo.LINE_CAP_BUTT)
        #game.cairo.set_line_width(1.0)

    def build_toolbar (self):
        self.editorbtn = gtk.ToggleToolButton()
        self.editorbtn.set_icon_name('media-playback-start')
        self.editorbtn.connect('clicked', self.on_toggle_editor)

        gamebox = gtk.Toolbar()
        gamebox.insert(self.editorbtn, -1)

        toolbar = activity.ActivityToolbox(self)
        toolbar.add_toolbar(_("Game"), gamebox)
        toolbar.show_all()
        self.set_toolbox(toolbar)

    def build_editor (self):
        self.editor = gtk.VBox()
        self.editor.set_size_request(800, 600)
        self.editor.set_property("spacing", 20)

        #  { 'Name': _('normal'), 'AISpeed': 1, 'AIRecenter': 1, 'StageDepth': 160, 'StageGravity': 0, 'StageCrossGravity': 0, 'BallSize': 1, 'BallSpeed': 3, 'PaddleWidth': 20, 'PaddleHeight': 20 },

        # Brush size scrollbar, label and pressure sensitivity checkbox.
        box = gtk.HBox()
        box.pack_end(gtk.Label(_('Name')), False)
        box.pack_end(gtk.HScale(gtk.Adjustment(50, 1, 260, 1, 10, 10)))
        self.editor.pack_start(box, False)

        box = gtk.HBox()
        box.pack_end(gtk.Label(_('AI Speed')), False)
        box.pack_end(gtk.HScale(gtk.Adjustment(50, 1, 260, 1, 10, 10)))
        self.editor.pack_start(box, False)

        box = gtk.HBox()
        box.pack_end(gtk.Label(_('Stage Depth')), False)
        box.pack_end(gtk.HScale(gtk.Adjustment(50, 1, 260, 1, 10, 10)))
        self.editor.pack_start(box, False)

        box = gtk.HBox()
        box.pack_end(gtk.Label(_('Gravity')), False)
        box.pack_end(gtk.HScale(gtk.Adjustment(50, 1, 260, 1, 10, 10)))
        self.editor.pack_start(box, False)

        box = gtk.HBox()
        box.pack_end(gtk.Label(_('Cross Gravity')), False)
        box.pack_end(gtk.HScale(gtk.Adjustment(50, 1, 260, 1, 10, 10)))
        self.editor.pack_start(box, False)

        box = gtk.HBox()
        box.pack_end(gtk.Label(_('Ball Size')), False)
        box.pack_end(gtk.HScale(gtk.Adjustment(50, 1, 260, 1, 10, 10)))
        self.editor.pack_start(box, False)

        box = gtk.HBox()
        box.pack_end(gtk.Label(_('Ball Speed')), False)
        box.pack_end(gtk.HScale(gtk.Adjustment(50, 1, 260, 1, 10, 10)))
        self.editor.pack_start(box, False)

        box = gtk.HBox()
        box.pack_end(gtk.Label(_('Paddle Width')), False)
        box.pack_end(gtk.HScale(gtk.Adjustment(50, 1, 260, 1, 10, 10)))
        self.editor.pack_start(box, False)

        box = gtk.HBox()
        box.pack_end(gtk.Label(_('Paddle Height')), False)
        box.pack_end(gtk.HScale(gtk.Adjustment(50, 1, 260, 1, 10, 10)))
        self.editor.pack_start(box, False)

        self.drawarea.put(self.editor, 25, 100)

    def on_toggle_editor (self, button):
        if button.get_active():
            self.paused = True
            self.editor.show()
            self.queue_draw()
            self.show_cursor(True)
        else:
            self.paused = False
            self.editor.hide()
            self.queue_draw()
            self.show_cursor(False)

    def show_cursor (self, show):
        if self.cursor_visible and not show:
            pixmap = gtk.gdk.Pixmap(None, 1, 1, 1)
            color = gtk.gdk.Color()
            cursor = gtk.gdk.Cursor(pixmap, pixmap, color, color, 0, 0)
            self.drawarea.bin_window.set_cursor(cursor)
        if not self.cursor_visible and show:
            self.drawarea.bin_window.set_cursor(None)
        self.cursor_visible = show

    def on_mouse (self, widget, event):
        game.mousex = int(event.x)
        game.mousey = int(event.y)
        if event.type == gtk.gdk.BUTTON_PRESS:
            # Simple cheat for testing.
            #if (game.paddle1.score < 5):
            #    game.paddle1.score += 1
            game.mousedown = 1
        if event.type == gtk.gdk.BUTTON_RELEASE:
            game.mousedown = 0

    def on_destroy (self, widget):
        self.running = False

    def tick (self):
        if self.paused:
            return True
        if not self.drawarea.bin_window:
            return True

        # Clear mouse cursor
        self.show_cursor(False)

        global actual_screen_width
        global actual_screen_height
        actual_screen_width = self.drawarea.get_allocation()[2]
        actual_screen_height = self.drawarea.get_allocation()[3]

        # Clear the offscreen surface.
        game.cairo.set_source_rgba(0, 0, 0)
        game.cairo.rectangle(0, 0, self.width, self.height)
        game.cairo.fill()

        # Update current game sequence and render into offscreen surface.
        game.sequence.update()
        game.sequence.draw()

        flush_prim()

        # Draw offscreen surface to screen.
        ctx = self.drawarea.bin_window.cairo_create()
        ctx.set_source_surface(game.cairosurf, 0, 0)
        ctx.rectangle(0, 0, self.width, self.height)
        ctx.fill()

        return True

    def mainloop (self):
        """Runs the game loop.  Note that this doesn't actually return until the activity ends."""
        self.running = True
        while self.running:
            self.tick()
            while gtk.events_pending():
                gtk.main_iteration(False)
        return False


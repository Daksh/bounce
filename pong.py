#!/usr/bin/env python
"""3dpong - 3D action game by Wade Brainerd."""

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

StageDescs = [
    { 'Name': _('normal'), 'AISpeed': 2, 'AIRecenter': 1, 'StageDepth': 160, 'StageGravity': 0, 'StageCrossGravity': 0, 'BallSpeed': 3, 'PlayerWidth': 40, 'PlayerHeight': 30, 'AIWidth': 40, 'AIHeight': 30 },
    { 'Name': _('bounce'), 'AISpeed': 4, 'AIRecenter': 1, 'StageDepth': 160, 'StageGravity': 1, 'StageCrossGravity': 0, 'BallSpeed': 3, 'PlayerWidth': 50, 'PlayerHeight': 40, 'AIWidth': 50, 'AIHeight': 40 },
    { 'Name': _('wide'),   'AISpeed': 8, 'AIRecenter': 1, 'StageDepth': 160, 'StageGravity': 1, 'StageCrossGravity': 0, 'BallSpeed': 4, 'PlayerWidth': 160, 'PlayerHeight': 20, 'AIWidth': 160, 'AIHeight': 20 },
    { 'Name': _('deep'),   'AISpeed': 10, 'AIRecenter': 0, 'StageDepth': 500, 'StageGravity': 0, 'StageCrossGravity': 0, 'BallSpeed': 10, 'PlayerWidth': 40, 'PlayerHeight': 50, 'AIWidth': 40, 'AIHeight': 40 },
    { 'Name': _('rotate'), 'AISpeed': 10, 'AIRecenter': 1, 'StageDepth': 160, 'StageGravity': 0, 'StageCrossGravity': 1, 'BallSpeed': 5, 'PlayerWidth': 40, 'PlayerHeight': 30, 'AIWidth': 40, 'AIHeight': 30 },
]

class VectorType:
    def __init__(self):
        self.X = 0
        self.Y = 0
        self.Z = 0

class RectType:
    def __init__(self):
        self.Top = 0
        self.Left = 0
        self.Right = 0
        self.Bottom = 0

ZeroVector3D = VectorType()

class BallType:
    def __init__(self):
        self.LastPos = VectorType()
        self.LastVel = VectorType()
        self.Pos = VectorType()
        self.Vel = VectorType()
    
class PaddleType:
    def __init__(self):
        # Center of the paddle
        self.Pos = VectorType()
        
        # Physics stuff
        self.Delta = VectorType() # Amount moved since last update for spin calc.
        self.HalfWidth = 0
        self.HalfHeight = 0

        # Stuff for moving the paddle forward.
        self.TargetZ = 0
        self.DefaultZ = 0
        self.ForwardZ = 0

        # AI stuff
        self.Vel = VectorType()
        self.Speed = 0

        # Game stuff
        self.Score = 0

class StageType:
    def __init__(self):
        # How long the stage is from near side to far side.
        self.Depth = 0
        self.Window = RectType()

        self.Gravity = 0
        self.CrossGravity = 0
        self.BallSpeed = 0
        self.BallSize = 5*256

class AIType:
    def __init__(self):
        self.Speed = 0
        self.Recenter = False

class GameType:
    def __init__(self):
        self.EndTimeout = 0

        self.AI = AIType()

        self.Stage = StageType()
        self.Ball = BallType()
        self.Paddle1 = PaddleType()
        self.Paddle2 = PaddleType()
        
        # Score variable from last frame, to see if we need to erase the scoring graphic.
        self.LastScore = 0
        
        # Current stage.
        self.CurLevel = 0

        # Variables affecting the sequencer.
        self.Sequence = 0
        #self.Sequence = 3  # Use to start at gameplay
        self.Brightness = 100
        self.Timer0 = 0;
        self.Timer1 = 0;
        
        # Current mouse state.
        self.MouseX = 0
        self.MouseY = 0
        self.MouseDown = 0

        self.XPoints = [ (0,0), (0.3,0), (0.5,0.3), (0.7,0), (1,0), (0.7,0.5), (1,1), (0.7,1), (0.5,0.6), (0.3,1), (0,1), (0.3,0.5) ]

Game = GameType()

# Virtual screen dimensions
# This game was ported from a Palm OS app, and it would be difficult to change all the internal calculations to a new resolution. 
ScreenWidth = 320
ScreenHeight = 240
ActualScreenWidth = 1200
ActualScreenHeight = 825

DisplayCenterX = 160*256
DisplayCenterY = 120*256

# Game constants
ViewportScale = 100*256
TimeRes = 32

def clamp(a, b, c):
    if (a<b): return b
    elif (a>c): return c
    else: return a

def max(a,b):
    if (a>b): return a
    else: return b
    
def GetProjectedX(X, Y, Z):
    return (DisplayCenterX + ( X - DisplayCenterX ) * ViewportScale / ( Z + ViewportScale )) * ActualScreenWidth/ScreenWidth / 256

def GetProjectedY(X, Y, Z):
    return (DisplayCenterY + ( Y - DisplayCenterY ) * ViewportScale / ( Z + ViewportScale )) * ActualScreenHeight/ScreenHeight / 256

def DrawLine3D(X1, Y1, Z1, X2, Y2, Z2, draw, color=None):
    if color == None: color = (255,255,255)
    Game.cairo.set_source_rgb(color[0]/255.0*Game.Brightness/100.0, color[1]/255.0*Game.Brightness/100.0, color[2]/255.0*Game.Brightness/100.0)
    Game.cairo.move_to(GetProjectedX( X1, Y1, Z1 ), GetProjectedY( X1, Y1, Z1 ))
    Game.cairo.line_to(GetProjectedX( X2, Y2, Z2 ), GetProjectedY( X2, Y2, Z2 ))
    Game.cairo.stroke()

def DrawRect3D(Rect, Depth, draw):
    Temp = RectType()

    Temp.Left = GetProjectedX( Rect.Left, Rect.Top, Depth ) + 1
    Temp.Top = GetProjectedY( Rect.Left, Rect.Top, Depth ) + 1
    Temp.Right = GetProjectedX( Rect.Right, Rect.Bottom, Depth ) - 1
    Temp.Bottom = GetProjectedY( Rect.Right, Rect.Bottom, Depth ) - 1

    Game.cairo.set_source_rgb(Game.Brightness/100.0, Game.Brightness/100.0, Game.Brightness/100.0)
    Game.cairo.move_to(Temp.Left, Temp.Top)
    Game.cairo.line_to(Temp.Right, Temp.Top)
    Game.cairo.line_to(Temp.Right, Temp.Bottom)
    Game.cairo.line_to(Temp.Left, Temp.Bottom)
    Game.cairo.line_to(Temp.Left, Temp.Top)
    Game.cairo.stroke()

def DrawCircle3D(X, Y, Z, radius, draw, color=None):
    if color == None: color = (255,255,255)
    r = GetProjectedX(X+radius, Y, Z)-GetProjectedX(X, Y, Z)
    if r < 1:
        return
    Game.cairo.set_source_rgb(color[0]/255.0*Game.Brightness/100.0, color[1]/255.0*Game.Brightness/100.0, color[2]/255.0*Game.Brightness/100.0)
    x = GetProjectedX( X, Y, Z )
    y = GetProjectedY( X, Y, Z )
    Game.cairo.move_to(x, y-r)
    Game.cairo.arc(x, y, r, 0, 2*math.pi)
    Game.cairo.stroke()

def DrawFilledCircle3D(X, Y, Z, radius, draw, color=None):
    if color == None: color = (255,255,255)
    r = GetProjectedX(X+radius, Y, Z)-GetProjectedX(X, Y, Z)
    if r < 1:
        return
    Game.cairo.set_source_rgb(color[0]/255.0*Game.Brightness/100.0, color[1]/255.0*Game.Brightness/100.0, color[2]/255.0*Game.Brightness/100.0)
    Game.cairo.arc(GetProjectedX( X, Y, Z ), GetProjectedY( X, Y, Z ), r, 0, 2*math.pi)
    Game.cairo.fill()

def DrawEllipse3D(X, Y, Z, radiusX, radiusY, draw, color=None):
    if (color == None): color = (255,255,255)
    w = radiusX*256/2/max(1,Z)
    h = radiusY*256/2/max(1,Z)
    #pygame.draw.ellipse(Game.screen, 
    #    (color[0]*Game.Brightness/100, color[1]*Game.Brightness/100, color[2]*Game.Brightness/100), 
    #    pygame.Rect(GetProjectedX( X, Y, Z )-w, GetProjectedY( X, Y, Z )-h, max(2,w*2), max(2,h*2)), 1) 

def DrawText (text, x, y, size):
    Game.cairo.set_font_size(size)
    x_bearing, y_bearing, width, height = Game.cairo.text_extents(text)[:4]
    if x == -1: x = ActualScreenWidth/2
    if y == -1: y = ActualScreenHeight/2
    Game.cairo.move_to(x - width/2 - x_bearing, y - height/2 - y_bearing)
    Game.cairo.show_text(text)

def DrawStage( Stage, draw ):
    Window = Stage.Window

    # Near and far rectangles   
    DrawRect3D( Window, 0, draw )
    DrawRect3D( Window, Stage.Depth, draw )

    # Diagonals
    DrawLine3D( Window.Left, Window.Top, 1, Window.Left, Window.Top, Stage.Depth, draw )
    DrawLine3D( Window.Left, Window.Bottom, 1, Window.Left, Window.Bottom, Stage.Depth, draw )
    DrawLine3D( Window.Right, Window.Top, 1, Window.Right, Window.Top, Stage.Depth, draw )
    DrawLine3D( Window.Right, Window.Bottom, 1, Window.Right, Window.Bottom, Stage.Depth, draw )

    i = 1
    while i < 5:
        x = i*(Window.Right-Window.Left)/5
        i += 1
        DrawLine3D(x, Window.Top, 1, x, Window.Top, Stage.Depth, draw, (64, 64, 64))
        DrawLine3D(x, Window.Bottom, 1, x, Window.Bottom, Stage.Depth, draw, (64, 64, 64))

    i = 1
    while i < 5:
        x = i*(Window.Bottom-Window.Top)/5
        i += 1
        DrawLine3D(Window.Left, x, 1, Window.Left, x, Stage.Depth, draw, (64, 64, 64))
        DrawLine3D(Window.Right, x, 1, Window.Right, x, Stage.Depth, draw, (64, 64, 64))
        
    i = 1
    while i < 5:
        x = i*(Stage.Depth)/5
        i += 1
        DrawLine3D(Window.Left, Window.Top, x, Window.Right, Window.Top, x, draw, (64, 64, 64))
        DrawLine3D(Window.Left, Window.Bottom, x, Window.Right, Window.Bottom, x, draw, (64, 64, 64))
        DrawLine3D(Window.Left, Window.Top, x, Window.Left, Window.Bottom, x, draw, (64, 64, 64))
        DrawLine3D(Window.Right, Window.Top, x, Window.Right, Window.Bottom, x, draw, (64, 64, 64))

def DrawBall( Ball, Stage, draw ):
    # Draw the ball.
    DrawFilledCircle3D(Ball.Pos.X, Ball.Pos.Y, Ball.Pos.Z, Game.Stage.BallSize, draw)

    # Draw the shadow.
    DrawEllipse3D(Ball.Pos.X, Stage.Window.Bottom, Ball.Pos.Z, Game.Stage.BallSize*2, Game.Stage.BallSize, draw, (64, 64, 64))

def DrawPaddle( Paddle, Stage, draw ):
    Temp = RectType()
    Temp.Left = Paddle.Pos.X - Paddle.HalfWidth 
    Temp.Right = Paddle.Pos.X + Paddle.HalfWidth    
    Temp.Top = Paddle.Pos.Y - Paddle.HalfHeight 
    Temp.Bottom = Paddle.Pos.Y + Paddle.HalfHeight  
    
    DrawRect3D( Temp, Paddle.Pos.Z, draw )

    DrawLine3D( 
        Temp.Left + ( ( Temp.Right - Temp.Left ) >> 1 ), Temp.Bottom, Paddle.Pos.Z,
        Temp.Left + ( ( Temp.Right - Temp.Left ) >> 1 ), Stage.Window.Bottom, Paddle.Pos.Z, draw )

# Check paddle inputs and apply to Paddle.
def UpdatePaddleFromPen ( Paddle, Stage ):
    LastPos = VectorType()
    LastPos.X = Paddle.Pos.X
    LastPos.Y = Paddle.Pos.Y
    LastPos.Z = Paddle.Pos.Z

    PenX = Game.MouseX*ScreenWidth/ActualScreenWidth
    PenY = Game.MouseY*ScreenHeight/ActualScreenHeight
    PenDown = 1

    if ( Game.MouseDown ):
        Paddle.TargetZ = Paddle.ForwardZ
    else:
        Paddle.TargetZ = Paddle.DefaultZ

    # Snaps forward, eases back.
    if ( Paddle.Pos.Z < Paddle.TargetZ ):
        if ( Paddle.Delta.Z < 4*256 ):
            Paddle.Delta.Z = 6*256
        Paddle.Pos.Z += Paddle.Delta.Z + 2*256
        if ( Paddle.Pos.Z > Paddle.TargetZ ):
            Paddle.Pos.Z = Paddle.TargetZ

    if ( Paddle.Pos.Z > Paddle.TargetZ ):
        Paddle.Pos.Z += ( Paddle.TargetZ - Paddle.Pos.Z ) / 4

    # Get the 2d position from the pen.
    if ( PenDown ): 
        Paddle.Pos.X = PenX*256
        Paddle.Pos.Y = PenY*256
        
        # Clip the paddle position.
        if ( Paddle.Pos.X < Paddle.HalfWidth ):
            Paddle.Pos.X = Paddle.HalfWidth

        if ( Paddle.Pos.Y < Paddle.HalfHeight ): 
            Paddle.Pos.Y = Paddle.HalfHeight

        if ( Paddle.Pos.X > Stage.Window.Right - Paddle.HalfWidth ):
            Paddle.Pos.X = Stage.Window.Right - Paddle.HalfWidth

        if ( Paddle.Pos.Y > Stage.Window.Bottom - Paddle.HalfHeight ):
            Paddle.Pos.Y = Stage.Window.Bottom - Paddle.HalfHeight

    Paddle.Delta.X = Paddle.Pos.X - LastPos.X
    Paddle.Delta.Y = Paddle.Pos.Y - LastPos.Y
    Paddle.Delta.Z = Paddle.Pos.Z - LastPos.Z

# Compute AI and move Paddle.
def UpdatePaddleAI( Paddle, Ball, Stage ):
    # Only move when the ball is coming back, that way it appears to react to the players hit.
    # Actually, start moving just before the player hits it.
    if ( Ball.Vel.Z > 0 or Ball.Vel.Z < 0 and Ball.Pos.Z < 30*256) :
        # Acceleration towards the ball.
        if ( math.fabs( ( Paddle.Pos.X - Ball.Pos.X ) ) > 5*256 ):
            if ( Paddle.Pos.X < Ball.Pos.X ):
                Paddle.Vel.X+=4*256
            if ( Paddle.Pos.X > Ball.Pos.X ):
                Paddle.Vel.X-=4*256
            
        if ( math.fabs( ( Paddle.Pos.Y - Ball.Pos.Y ) ) > 5*256 ):
            if ( Paddle.Pos.Y < Ball.Pos.Y ):
                Paddle.Vel.Y+=4*256
            if ( Paddle.Pos.Y > Ball.Pos.Y ): 
                Paddle.Vel.Y-=4*256
        
        # Speed clamping
        Paddle.Vel.X = clamp( Paddle.Vel.X, -Game.AI.Speed, Game.AI.Speed )
        Paddle.Vel.Y = clamp( Paddle.Vel.Y, -Game.AI.Speed, Game.AI.Speed )
    elif ( Ball.Pos.Z < Game.Stage.Depth/2 ):
        Paddle.Vel.X = 0
        Paddle.Vel.Y = 0
        # Drift towards the center.
        if ( Game.AI.Recenter ):
            Paddle.Pos.X += ( ScreenWidth/2*256 - Paddle.Pos.X ) / 4
            Paddle.Pos.Y += ( ScreenWidth/2*256 - Paddle.Pos.Y ) / 4
            
    # Friction
    if ( Paddle.Vel.X > 0 ):
        Paddle.Vel.X -= 1
    if ( Paddle.Vel.X < 0 ):
        Paddle.Vel.X += 1
        
    if ( Paddle.Vel.Y > 0 ):
        Paddle.Vel.Y -= 1
    if ( Paddle.Vel.Y < 0 ):
        Paddle.Vel.Y += 1
        
    Paddle.Pos.X += Paddle.Vel.X
    Paddle.Pos.Y += Paddle.Vel.Y
    
    # Clip the paddle position
    if ( Paddle.Pos.X < Paddle.HalfWidth ): Paddle.Pos.X = Paddle.HalfWidth
    if ( Paddle.Pos.Y < Paddle.HalfHeight ): Paddle.Pos.Y = Paddle.HalfHeight
    if ( Paddle.Pos.X > Stage.Window.Right - Paddle.HalfWidth ): Paddle.Pos.X = Stage.Window.Right - Paddle.HalfWidth
    if ( Paddle.Pos.Y > Stage.Window.Bottom - Paddle.HalfHeight ): Paddle.Pos.Y = Stage.Window.Bottom - Paddle.HalfHeight

# 0 if nobody scored, 1 if Paddle1 scored, 2 if Paddle2 scored.
def UpdateBall ( Ball, Paddle1, Paddle2, Stage ):
    # Ball collisions are handled very accurately, as this is the basis of the game.
    # All times are in 1sec/TimeRes units.
    # 1. Loop through all the surfaces and finds the first one the ball will collide with
    # in this animation frame (if any). 
    # 2. Update the Ball velocity based on the collision, and advance the current time to 
    # the exact time of the collision.
    # 3. Goto step 1, until no collisions remain in the current animation frame.

    TimeLeft = TimeRes                  # Time remaining in this animation frame.
    FirstCollisionTime = 0              # -1 means no collision found.
    FirstCollisionVel = VectorType()    # New ball velocity from first collision.
    FirstCollisionType = 0              # 0 for normal collision (wall), otherwise the scorezone number hit. 

    Ball.LastPos.X = Ball.Pos.X
    Ball.LastPos.Y = Ball.Pos.Y
    Ball.LastPos.Z = Ball.Pos.Z
    Ball.LastVel.X = Ball.Vel.X
    Ball.LastVel.Y = Ball.Vel.Y
    Ball.LastVel.Z = Ball.Vel.Z

    NextBallPos = VectorType()          # Hypothetical ball position assuming no collision.
    Time = 0                            # Time of current collision.
    
    CollisionType = 0                   # Stored return value.

    Iterations = 0

    while True:
        Iterations = Iterations+1
        if ( Iterations > 5 ):
            break

        # Calculate new next ball position.
        NextBallPos.X = Ball.Pos.X + (Ball.Vel.X * TimeLeft) / TimeRes
        NextBallPos.Y = Ball.Pos.Y + (Ball.Vel.Y * TimeLeft) / TimeRes
        NextBallPos.Z = Ball.Pos.Z + (Ball.Vel.Z * TimeLeft) / TimeRes

        # Reset FirstCollisionTime.     
        FirstCollisionTime = -1

        # Check stage walls.  First checks to see if the boundary was crossed, if so then calculates time, etc.
        if ( NextBallPos.X - Game.Stage.BallSize <= 0 ): # Left wall
            Time = ( Ball.Pos.X - Game.Stage.BallSize ) * TimeRes / -Ball.Vel.X # negative VX is to account for left wall facing.
            if ( FirstCollisionTime == -1 or Time < FirstCollisionTime ):
                # Set new first collision.
                FirstCollisionTime = Time
                FirstCollisionVel.X = -Ball.Vel.X
                FirstCollisionVel.Y = Ball.Vel.Y
                FirstCollisionVel.Z = Ball.Vel.Z
                FirstCollisionType = 5
        if ( NextBallPos.X + Game.Stage.BallSize >= Stage.Window.Right ): # Right wall
            Time = ( Stage.Window.Right - ( Ball.Pos.X + Game.Stage.BallSize ) ) * TimeRes / Ball.Vel.X
            if ( FirstCollisionTime == -1 or Time < FirstCollisionTime ):
                # Set new first collision.
                FirstCollisionTime = Time
                FirstCollisionVel.X = -Ball.Vel.X
                FirstCollisionVel.Y = Ball.Vel.Y
                FirstCollisionVel.Z = Ball.Vel.Z
                FirstCollisionType = 5
        if ( NextBallPos.Y - Game.Stage.BallSize <= 0 and Ball.Vel.Y != 0): # Top wall
            Time = ( Ball.Pos.Y - Game.Stage.BallSize ) * TimeRes / -Ball.Vel.Y
            if ( FirstCollisionTime == -1 or Time < FirstCollisionTime ):
                # Set new first collision.
                FirstCollisionTime = Time
                FirstCollisionVel.X = Ball.Vel.X
                FirstCollisionVel.Y = -Ball.Vel.Y
                FirstCollisionVel.Z = Ball.Vel.Z
                FirstCollisionType = 5
        if ( NextBallPos.Y + Game.Stage.BallSize >= Stage.Window.Bottom  and Ball.Vel.Y != 0): # Bottom wall
            Time = ( Stage.Window.Bottom - ( Ball.Pos.Y + Game.Stage.BallSize ) ) * TimeRes / Ball.Vel.Y
            if ( FirstCollisionTime == -1 or Time < FirstCollisionTime ):
                # Set new first collision.
                FirstCollisionTime = Time
                FirstCollisionVel.X = Ball.Vel.X
                FirstCollisionVel.Y = -Ball.Vel.Y
                FirstCollisionVel.Z = Ball.Vel.Z
                FirstCollisionType = 5
        if ( NextBallPos.Z <= 0 ): # Front wall
            Time = Ball.Pos.Z * TimeRes / -Ball.Vel.Z
            if ( FirstCollisionTime == -1 or Time < FirstCollisionTime ):
                # Set new first collision.
                FirstCollisionTime = Time
                FirstCollisionVel.X = Ball.Vel.X #(random.randint(0, 3))-1 * Game.Stage.BallSpeed
                FirstCollisionVel.Y = Ball.Vel.Y #(random.randint(0, 3))-1 * Game.Stage.BallSpeed
                FirstCollisionVel.Z = Game.Stage.BallSpeed
                FirstCollisionType = 2
        if ( NextBallPos.Z >= Stage.Depth ): # Back wall
            Time = ( Stage.Depth - Ball.Pos.Z ) * TimeRes / Ball.Vel.Z
            if ( FirstCollisionTime == -1 or Time < FirstCollisionTime ):
                # Set new first collision.
                FirstCollisionTime = Time
                FirstCollisionVel.X = Ball.Vel.X #(random.randint(0, 3))-1 * Game.Stage.BallSpeed
                FirstCollisionVel.Y = Ball.Vel.Y #(random.randint(0, 3))-1 * Game.Stage.BallSpeed
                FirstCollisionVel.Z = -Game.Stage.BallSpeed
                FirstCollisionType = 1
        # Paddle collision.  Paddle collisions are inaccurate, in that it doesn't take into account the velocity of 
        # the ball in its 2D check, it uses the original 2D position.
        if (        Ball.Vel.Z < 0 
                and ( Ball.Pos.Z >= Paddle1.Pos.Z or Ball.Pos.Z >= Paddle1.Pos.Z - math.fabs(Paddle1.Delta.Z) ) 
                and ( NextBallPos.Z <= Paddle1.Pos.Z or NextBallPos.Z <= Paddle1.Pos.Z + math.fabs(Paddle1.Delta.Z) )
                and Ball.Pos.X >= Paddle1.Pos.X - Paddle1.HalfWidth
                and Ball.Pos.X <= Paddle1.Pos.X + Paddle1.HalfWidth 
                and Ball.Pos.Y >= Paddle1.Pos.Y - Paddle1.HalfHeight
                and Ball.Pos.Y <= Paddle1.Pos.Y + Paddle1.HalfHeight ):
            Time = ( Ball.Pos.Z - Paddle1.Pos.Z ) * TimeRes / -Ball.Vel.Z
            if ( FirstCollisionTime == -1 or Time <= FirstCollisionTime ):
                # Set new first collision.
                FirstCollisionTime = Time
                FirstCollisionVel.X = Ball.Vel.X
                FirstCollisionVel.Y = Ball.Vel.Y
                FirstCollisionVel.Z = -Ball.Vel.Z

                # If paddle is moving forward, bounce the ball off.
                if ( Paddle1.Delta.Z > 0 ):
                    FirstCollisionVel.Z += 4*246

                    # Apply some pong like angling based on where it hits the paddle.
                    if ( NextBallPos.X - Paddle1.Pos.X > 20 ):
                        FirstCollisionVel.X += 2*256
                    if ( NextBallPos.X - Paddle1.Pos.X < -20 ):
                        FirstCollisionVel.X -= 2*256

                    if ( NextBallPos.Y - Paddle1.Pos.Y > 15 ):
                        FirstCollisionVel.Y += 2*256
                    if ( NextBallPos.Y - Paddle1.Pos.Y < -15 ):
                        FirstCollisionVel.Y -= 2*256
                # Likewise if paddle is moving backwards, cushion it.
                if ( Paddle1.Delta.Z < 0 ):
                    FirstCollisionVel.Z -= 2*256
                
                FirstCollisionType = 3
        # Computer paddle.
        if (        Ball.Vel.Z > 0 
                and ( Ball.Pos.Z <= Paddle2.Pos.Z ) 
                and ( NextBallPos.Z >= Paddle2.Pos.Z )
                and Ball.Pos.X >= Paddle2.Pos.X - Paddle2.HalfWidth
                and Ball.Pos.X <= Paddle2.Pos.X + Paddle2.HalfWidth 
                and Ball.Pos.Y >= Paddle2.Pos.Y - Paddle2.HalfHeight
                and Ball.Pos.Y <= Paddle2.Pos.Y + Paddle2.HalfHeight ): # Paddle 2
            Time = ( Paddle2.Pos.Z - Ball.Pos.Z ) * TimeRes / Ball.Vel.Z
            if ( FirstCollisionTime == -1 or Time <= FirstCollisionTime ):
                # Set new first collision.
                FirstCollisionTime = Time
                FirstCollisionVel.X = Ball.Vel.X
                FirstCollisionVel.Y = Ball.Vel.Y
                FirstCollisionVel.Z = -Ball.Vel.Z + ( Paddle1.Delta.Z > 0 ) * 2*256 + ( Paddle1.Delta.Z < 0 ) * 2*256
                FirstCollisionType = 4

        # Advance the ball to the point of the first collision.
        if ( FirstCollisionTime != -1 ):
            Ball.Pos.X += Ball.Vel.X * FirstCollisionTime / TimeRes
            Ball.Pos.Y += Ball.Vel.Y * FirstCollisionTime / TimeRes
            Ball.Pos.Z += Ball.Vel.Z * FirstCollisionTime / TimeRes
            Ball.Vel.X = FirstCollisionVel.X
            Ball.Vel.Y = FirstCollisionVel.Y
            Ball.Vel.Z = FirstCollisionVel.Z
            
            TimeLeft -= FirstCollisionTime
            CollisionType = FirstCollisionType
        if ( not (FirstCollisionTime != -1 and TimeLeft > 0) ):
            break

    # If there's time left in the frame w/o collision, finish it up.    
    if TimeLeft > 0:
        Ball.Pos.X += Ball.Vel.X * TimeLeft / TimeRes
        Ball.Pos.Y += Ball.Vel.Y * TimeLeft / TimeRes
        Ball.Pos.Z += Ball.Vel.Z * TimeLeft / TimeRes

    # Apply gravity.
    Ball.Vel.Y += Game.Stage.Gravity
    if ( Ball.Pos.Y + Game.Stage.BallSize + 20 > Stage.Window.Bottom and math.fabs(Ball.Vel.Y) == 0 ):
        Ball.Vel.Y -= 6
    Ball.Vel.X += Game.Stage.CrossGravity

    # Calculate scores if any collisions with the back wall happened.
    if CollisionType == 1:
        Paddle1.Score += 1
    elif CollisionType == 2:
        Paddle2.Score += 1  
    #elif CollisionType == 3:
    #    Game.Player1PaddleWav.play()    
    #elif CollisionType == 4:
    #    Game.Player2PaddleWav.play()    
    #elif CollisionType == 5:
    #    Game.WallWav.play() 
        
    return CollisionType

def InitStage(depth, grav, speed):
    Game.Stage.Gravity = grav
    Game.Stage.BallSpeed = speed
    Game.Stage.Depth = depth
    Game.Stage.Window.Left = 0
    Game.Stage.Window.Right = ScreenWidth*256 - 1
    Game.Stage.Window.Top = 0
    Game.Stage.Window.Bottom = ScreenHeight*256 - 1

    Game.Ball.Pos.X = ScreenWidth/2*256
    Game.Ball.Pos.Y = ScreenHeight*1/4*256
    Game.Ball.Pos.Z = Game.Stage.Depth/2
    Game.Ball.Vel.X = 2*256 #(random.randint(0, 3))-1 * speed
    Game.Ball.Vel.Y = 2*256 #(random.randint(0, 3))-1 * speed
    Game.Ball.Vel.Z = speed

def InitPlayerPaddle( w, h ):
    Game.Paddle1.Score = 0
    Game.Paddle1.HalfWidth = w
    Game.Paddle1.HalfHeight = h
    Game.Paddle1.Pos.X = ScreenWidth*1/4*256
    Game.Paddle1.Pos.Y = ScreenHeight/2*256
    Game.Paddle1.Pos.Z = 10*256
    Game.Paddle1.DefaultZ = Game.Paddle1.Pos.Z
    Game.Paddle1.TargetZ = Game.Paddle1.Pos.Z
    Game.Paddle1.ForwardZ = 40*256
    Game.Paddle1.Delta = ZeroVector3D

    # Clip the paddle position
    Paddle = Game.Paddle1
    if ( Paddle.Pos.X < Paddle.HalfWidth ): Paddle.Pos.X = Paddle.HalfWidth
    if ( Paddle.Pos.Y < Paddle.HalfHeight ): Paddle.Pos.Y = Paddle.HalfHeight
    if ( Paddle.Pos.X > Game.Stage.Window.Right - Paddle.HalfWidth ): Paddle.Pos.X = Game.Stage.Window.Right - Paddle.HalfWidth
    if ( Paddle.Pos.Y > Game.Stage.Window.Bottom - Paddle.HalfHeight ): Paddle.Pos.Y = Game.Stage.Window.Bottom - Paddle.HalfHeight

def InitAIPaddle( w, h ):
    Game.Paddle2.Score = 0
    Game.Paddle2.HalfWidth = w
    Game.Paddle2.HalfHeight = h
    Game.Paddle2.Pos.X = ScreenWidth*3/4*256
    Game.Paddle2.Pos.Y = ScreenHeight/2*256
    Game.Paddle2.Pos.Z = Game.Stage.Depth - 10*256
    Game.Paddle2.DefaultZ = Game.Paddle2.Pos.Z
    Game.Paddle2.TargetZ = Game.Paddle2.Pos.Z
    Game.Paddle2.ForwardZ = Game.Stage.Depth - 40*256
    Game.Paddle2.Delta = ZeroVector3D
    Game.Paddle2.Vel = ZeroVector3D

    # Clip the paddle position
    Paddle = Game.Paddle2
    if ( Paddle.Pos.X < Paddle.HalfWidth ): Paddle.Pos.X = Paddle.HalfWidth
    if ( Paddle.Pos.Y < Paddle.HalfHeight ): Paddle.Pos.Y = Paddle.HalfHeight
    if ( Paddle.Pos.X > Game.Stage.Window.Right - Paddle.HalfWidth ): Paddle.Pos.X = Game.Stage.Window.Right - Paddle.HalfWidth
    if ( Paddle.Pos.Y > Game.Stage.Window.Bottom - Paddle.HalfHeight ): Paddle.Pos.Y = Game.Stage.Window.Bottom - Paddle.HalfHeight

def NextLevel():
    StageDesc = StageDescs[Game.CurLevel]
    Game.Stage.Name = StageDesc['Name']
    Game.Stage.BallSize = 5*256
    Game.AI.Speed = StageDesc['AISpeed']*256
    Game.AI.Recenter = StageDesc['AIRecenter']
    InitStage(StageDesc['StageDepth']*256, StageDesc['StageGravity']*256, StageDesc['BallSpeed']*256)
    Game.Stage.CrossGravity = StageDesc['StageCrossGravity']*256
    InitPlayerPaddle(StageDesc['PlayerWidth']*256, StageDesc['PlayerHeight']*256)
    InitAIPaddle(StageDesc['AIWidth']*256, StageDesc['AIHeight']*256)

def NewGame():
    Game.CurLevel = 0
    NextLevel()

def DrawScoreBar(Pos, Score, Color, Player):
    Game.cairo.set_source_rgb(Color[0]/255.0, Color[1]/255.0, Color[2]/255.0)
    if Player == 0:
        for j in range(0, 5):
            x = Pos[0] + j*30
            y = Pos[1]
            Game.cairo.move_to(Game.XPoints[0][0]*20-10+x, Game.XPoints[0][1]*20-10+y)
            for p in Game.XPoints:
                Game.cairo.line_to(p[0]*20-10+x, p[1]*20-10+y)
            Game.cairo.line_to(Game.XPoints[0][0]*20-10+x, Game.XPoints[0][1]*20-10+y)
            if j >= Score:
                Game.cairo.stroke()
            else:
                Game.cairo.fill()
    else:
        for j in range(0, 5):
            Game.cairo.move_to(Pos[0] + j*30 + 10, Pos[1])
            Game.cairo.arc(Pos[0] + j*30, Pos[1], 10, 0, 2*math.pi)
            if j >= Score:
                Game.cairo.stroke()
            else:
                Game.cairo.fill()

def DrawGame():
    DrawStage( Game.Stage, 1 )
    DrawPaddle( Game.Paddle1, Game.Stage, 1 )
    DrawPaddle( Game.Paddle2, Game.Stage, 1 )
    DrawBall( Game.Ball, Game.Stage, 1 )

    v = 255*Game.Brightness/100.0
    color = (v, v, v)

    DrawScoreBar((ActualScreenWidth*1/4-75, 30), Game.Paddle1.Score, color, 0)
    DrawScoreBar((ActualScreenWidth*3/4-75, 30), Game.Paddle2.Score, color, 1)

    #Game.cairo.set_source_rgb(color[0]/255.0, color[1]/255.0, color[2]/255.0)
    #DrawText(StageDescs[Game.CurLevel]['Name'], -1, 30, 24)

def DrawScoreEffect():
    RingSpacing = 8*256
    RingSpeed = 3*256
    NumRings = 10
    NumSteps = 20
    #clock = time.clock()
    #Game.ScoreWav.play()
    for step in range(1, NumSteps):
        Game.cairo.set_source_rgba(0, 0, 0)
        Game.cairo.rectangle(0, 0, ActualScreenWidth, ActualScreenHeight)
        Game.cairo.fill()
        b = 255*(1.0-float(step)/NumSteps)
        DrawCircle3D(Game.Ball.LastPos.X+Game.Ball.LastVel.X*step/2, Game.Ball.LastPos.Y+Game.Ball.LastVel.Y*step/2, Game.Ball.LastPos.Z+Game.Ball.LastVel.Z*step/2, Game.Stage.BallSize, True, (b,b,b))
        random.seed(12345678)
        for ring in range(0, NumRings):
            b = 255*(1.0-float(step)/NumSteps)*(0.5+0.5*math.cos(math.pi*float(ring)/NumRings))
            DrawCircle3D(Game.Ball.LastPos.X+Game.Ball.LastVel.X*ring, Game.Ball.LastPos.Y+Game.Ball.LastVel.Y*ring, Game.Ball.LastPos.Z+Game.Ball.LastVel.Z*ring, (-ring+1)*RingSpacing + RingSpeed*step, True, (b, b, b))
        DrawGame()
        time.sleep(0.01)
        #pygame.display.flip()
        #clock.tick(20)

def SequenceIntro():
    if (Game.Timer1 == 0):
        Game.Brightness = 0
        Game.Timer0 += 1
        if (Game.Timer0 >= 100):
            Game.Timer1 = 1
    elif (Game.Timer1 == 1):
        if (Game.Brightness < 100): Game.Brightness += 1
        Game.Timer0 -= 2
        if (Game.Timer0 <= 0):
            #Game.IntroWav.play()
            Game.Sequence = 2
            Game.Timer0 = 0
            Game.Timer1 = 0
        DrawGame()
    Game.cairo.set_source_rgb(Game.Timer0/100.0, Game.Timer0/100.0, Game.Timer0/100.0)
    DrawText("3 d   p o n g", -1, -1, 100)

def SequenceNewStage():
    DrawGame()
    if (Game.Timer1 == 0):
        if (Game.Brightness > 0): Game.Brightness -= 5
        Game.Timer0 += 2
        if (Game.Timer0 >= 100):
            Game.Timer1 = 1
            NextLevel()
    elif (Game.Timer1 == 1):
        if (Game.Brightness < 100): Game.Brightness += 1
        Game.Timer0 -= 2
        if (Game.Timer0 <= 0):
            #Game.IntroWav.play()
            Game.Sequence = 2
            Game.Timer0 = 0
            Game.Timer1 = 0
    Game.cairo.set_source_rgb(Game.Timer0/100.0, Game.Timer0/100.0, Game.Timer0/100.0)
    DrawText(StageDescs[Game.CurLevel]['Name'], -1, -1, 100)

def SequenceBallRelease():
    if (Game.Brightness < 100): Game.Brightness += 1
    DrawGame()
    v = math.sin(3.14159*Game.Timer0/30.0)
    Game.Timer0 += 1
    if (Game.Timer0 > 25):
        Game.Timer1 += 1
        Game.Timer0 = 0
    if (Game.Timer1 >= 3):
        Game.Sequence = 3
        Game.EndTimeout = 0
    Game.cairo.set_source_rgb(v, v, v)
    DrawText(str(3-Game.Timer1), -1, -1, 20)

def SequencePlay():
    DrawGame()
    
    # Process player input and AI.
    UpdatePaddleFromPen( Game.Paddle1, Game.Stage )
    UpdatePaddleAI( Game.Paddle2, Game.Ball, Game.Stage )
    
    # Run the ball simulation.
    Game.LastScore = UpdateBall( Game.Ball, Game.Paddle1, Game.Paddle2, Game.Stage )
    if ( Game.LastScore == 1 ):
        DrawScoreEffect()
    if ( Game.LastScore == 2 ):
        DrawScoreEffect()
        
    # Check for end of game conditions.
    if ( Game.Paddle1.Score == 5 or Game.Paddle2.Score == 5 ):
        Game.EndTimeout += 1
    if ( Game.EndTimeout >= 5 ):
        StageDescs[Game.CurLevel]['PlayerScore'] = Game.Paddle1.Score
        StageDescs[Game.CurLevel]['AIScore'] = Game.Paddle2.Score
        if ( Game.Paddle2.Score == 5 ):
            Game.Sequence = 4
            Game.Timer0 = 0
            Game.Timer1 = 0
        if ( Game.Paddle1.Score == 5 ):
            Game.CurLevel += 1
            if (Game.CurLevel == len(StageDescs)):
                Game.Timer0 = 0
                Game.Timer1 = 0
                Game.Sequence = 5
            else:
                Game.Timer0 = 0
                Game.Timer1 = 0
                Game.Sequence = 1

def SequenceGameOver():
    DrawGame()
    Game.cairo.set_source_rgb(Game.Timer0/100, Game.Timer0/100, Game.Timer0/100)
    DrawText("; - {", -1, -1, 24)
    if (Game.Timer1 == 0):
        if (Game.Brightness > 0): Game.Brightness -= 5
        Game.Timer0 += 2
        if (Game.Timer0 >= 100):
            Game.Timer1 = 1
            NewGame()
    elif (Game.Timer1 == 1):
        Game.Timer0 -= 2
        if (Game.Timer0 <= 0):
            Game.Sequence = 0
            Game.Timer0 = 0
            Game.Timer1 = 0

def SequenceYouWin():
    StartY = 250
    TotalScore = 0
    for i in range(0, len(StageDescs)):
        v = clamp(255*Game.Timer0/60.0 - i*60, 0, 255)
        color = (v, v, v)

        PlayerScore = StageDescs[i]['PlayerScore']
        AIScore = StageDescs[i]['AIScore']
        DiffScore = PlayerScore - AIScore

        DrawScoreBar((250, StartY + i*50), PlayerScore, color, 0)
        DrawText('-', 475, StartY + i*50, 20)
        DrawScoreBar((550, StartY + i*50), AIScore, color, 1)
        DrawText('=', 775, StartY + i*50, 20)
        DrawScoreBar((850, StartY + i*50), DiffScore, color, 0)

        DrawText(StageDescs[i]['Name'], 125, StartY + i*50, 24)

        TotalScore += DiffScore

    Game.cairo.move_to(250, StartY + len(StageDescs)*50)
    Game.cairo.line_to(950, StartY + len(StageDescs)*50)
    Game.cairo.stroke()
    x = 250
    y = StartY + (len(StageDescs)+1)*50
    for j in range(0, 5*len(StageDescs)):
        Game.cairo.move_to(Game.XPoints[0][0]*20-10+x, Game.XPoints[0][1]*20-10+y)
        for p in Game.XPoints:
            Game.cairo.line_to(p[0]*20-10+x, p[1]*20-10+y)
        Game.cairo.line_to(Game.XPoints[0][0]*20-10+x, Game.XPoints[0][1]*20-10+y)
        if j >= TotalScore:
            Game.cairo.stroke()
        else:
            Game.cairo.fill()
        x += 30
        if (x > 980):
            x = 250
            y += 50

    text = "; - |"
    if (TotalScore >= 5*len(StageDescs)):
        text = "; - D"
    elif (TotalScore >= 4*len(StageDescs)):
        text = "; - >"
    elif (TotalScore >= 3*len(StageDescs)):
        text = "; - )"
    elif (TotalScore >= 2*len(StageDescs)):
        text = "; - }"
    DrawText(text, -1, 150, 24)

    if (Game.Timer1 == 0):
        if (Game.Brightness > 0): Game.Brightness -= 5
        if (Game.Brightness <= 0):
            Game.Timer0 = 0
            Game.Timer1 = 1
        DrawGame()
    elif (Game.Timer1 == 1):
        Game.Timer0 += 1                
        if (Game.Timer0 >= 1000 or Game.MouseDown):
            Game.Timer1 = 2
            Game.Timer0 = len(StageDescs)*30
    elif (Game.Timer1 == 2):
        Game.Timer0 -= 1
        if (Game.Timer0 <= 0):
            NewGame()
            Game.Sequence = 0
            Game.Timer0 = 0
            Game.Timer1 = 0

class Pong3D(activity.Activity):

    def __init__ (self, handle):
        activity.Activity.__init__(self, handle)
        self.set_title(_("3dpong"))

        # Get activity size. 
        # todo- What we really need is the size of the canvasarea, not including the toolbox.
        self.width = gtk.gdk.screen_width()
        self.height = gtk.gdk.screen_height()

        global ActualScreenWidth
        global ActualScreenHeight
        ActualScreenWidth = self.width
        ActualScreenHeight = self.height

        # Set up the drawing window.
        self.drawarea = gtk.DrawingArea()
        self.drawarea.set_size_request(self.width, self.height)
        self.drawarea.connect('destroy', self.on_destroy)
        self.drawarea.add_events(gtk.gdk.POINTER_MOTION_MASK|gtk.gdk.BUTTON_PRESS_MASK|gtk.gdk.BUTTON_RELEASE_MASK)
        self.drawarea.connect('motion-notify-event', self.on_mouse)
        self.drawarea.connect('button-press-event', self.on_mouse)
        self.drawarea.connect('button-release-event', self.on_mouse)
        self.drawarea.grab_add()
        self.drawarea.cursor_initialized = False

        self.set_double_buffered(False)
        self.drawarea.set_double_buffered(True)

        # Set up the drawing.
        self.set_canvas(self.drawarea)
        self.show_all()

        # Initialize the game.
        NewGame()

        # Get the mainloop ready to run.
        gobject.timeout_add(50, self.mainloop)

    def mainloop (self):
        # Start the game loop.  Note that __init__ doesn't actually return until the activity ends.  
        # A bit extreme, but it's the only way to take over the GTK event loop from an Activity.
        self.running = True
        while self.running:
            self.tick()
            while gtk.events_pending():
                gtk.main_iteration(False)
        return False

    def on_mouse (self, widget, event):
        Game.MouseX = int(event.x)
        Game.MouseY = int(event.y)
        if event.type == gtk.gdk.BUTTON_PRESS:
            #if (Game.Paddle1.Score < 5):
            #    Game.Paddle1.Score += 1
            Game.MouseDown = 1
        if event.type == gtk.gdk.BUTTON_RELEASE:
            Game.MouseDown = 0

    def on_destroy (self, widget):
        self.running = False

    def tick (self):
        # Clear mouse cursor
        if not self.drawarea.window:
            return True
        if not self.drawarea.cursor_initialized:
            self.drawarea.cursor_initialized = True
            pixmap = gtk.gdk.Pixmap(None, 1, 1, 1)
            color = gtk.gdk.Color()
            cursor = gtk.gdk.Cursor(pixmap, pixmap, color, color, 0, 0)
            self.drawarea.window.set_cursor(cursor)

        self.drawareactx = self.drawarea.window.cairo_create()

        Game.cairosurf = cairo.ImageSurface(cairo.FORMAT_RGB24, self.width, self.height)
        Game.cairo = cairo.Context(Game.cairosurf)

        Game.cairo.set_antialias(cairo.ANTIALIAS_NONE)
        #Game.cairo.set_line_cap(cairo.LINE_CAP_BUTT)
        #Game.cairo.set_line_width(1.0)

        # Clear the screen.
        Game.cairo.set_source_rgba(0, 0, 0)
        Game.cairo.rectangle(0, 0, self.width, self.height)
        Game.cairo.fill()

        # Handle current game sequence.
        if (Game.Sequence == 0): # Intro
            SequenceIntro()
        elif (Game.Sequence == 1): # New stage
            SequenceNewStage()
        elif (Game.Sequence == 2): # Ball release
            SequenceBallRelease()
        elif (Game.Sequence == 3): # Play
            SequencePlay()
        elif (Game.Sequence == 4): # Game over
            SequenceGameOver()
        elif (Game.Sequence == 5): # You Win
            SequenceYouWin()

        self.drawareactx.set_source_surface(Game.cairosurf, 0, 0)
        self.drawareactx.rectangle(0, 0, self.width, self.height)
        self.drawareactx.fill()

        return True


#! /usr/bin/env python
"""3D Pong action game"""
import olpcgames, pygame, logging, random, math
from pygame.locals import *

log = logging.getLogger( '3dpong run' )
log.setLevel( logging.DEBUG )

StageDescs = [
    { 'Name': '+0', 'AISpeed': 2, 'AIRecenter': 1, 'StageDepth': 160, 'StageGravity': 0, 'StageCrossGravity': 0, 'BallSpeed': 3, 'PlayerWidth': 40, 'PlayerHeight': 30, 'AIWidth': 40, 'AIHeight': 30 },
    { 'Name': '+1', 'AISpeed': 4, 'AIRecenter': 1, 'StageDepth': 160, 'StageGravity': 1, 'StageCrossGravity': 0, 'BallSpeed': 3, 'PlayerWidth': 50, 'PlayerHeight': 40, 'AIWidth': 50, 'AIHeight': 40 },
    { 'Name': '+2', 'AISpeed': 8, 'AIRecenter': 1, 'StageDepth': 160, 'StageGravity': 1, 'StageCrossGravity': 0, 'BallSpeed': 4, 'PlayerWidth': 160, 'PlayerHeight': 15, 'AIWidth': 160, 'AIHeight': 15 },
    { 'Name': '+3', 'AISpeed': 10, 'AIRecenter': 0, 'StageDepth': 500, 'StageGravity': 0, 'StageCrossGravity': 0, 'BallSpeed': 10, 'PlayerWidth': 40, 'PlayerHeight': 50, 'AIWidth': 40, 'AIHeight': 40 },
    { 'Name': '+4', 'AISpeed': 10, 'AIRecenter': 1, 'StageDepth': 160, 'StageGravity': 0, 'StageCrossGravity': 1, 'BallSpeed': 5, 'PlayerWidth': 40, 'PlayerHeight': 30, 'AIWidth': 40, 'AIHeight': 30 },
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
        #self.Sequence = 3  # Use to start at gameplay
        self.Sequence = 0
        self.Brightness = 100 # 0
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
    if (color == None): color = (255,255,255)
    pygame.draw.line(Game.screen, 
        (color[0]*Game.Brightness/100, color[1]*Game.Brightness/100, color[2]*Game.Brightness/100), 
        (GetProjectedX( X1, Y1, Z1 ), GetProjectedY( X1, Y1, Z1 )), 
        (GetProjectedX( X2, Y2, Z2 ), GetProjectedY( X2, Y2, Z2 )))

def DrawRect3D(Rect, Depth, draw):
    Temp = RectType()

    Temp.Left = GetProjectedX( Rect.Left, Rect.Top, Depth ) + 1
    Temp.Top = GetProjectedY( Rect.Left, Rect.Top, Depth ) + 1
    Temp.Right = GetProjectedX( Rect.Right, Rect.Bottom, Depth ) - 1
    Temp.Bottom = GetProjectedY( Rect.Right, Rect.Bottom, Depth ) - 1

    if ( draw ):
        pygame.draw.rect(Game.screen, (255*Game.Brightness/100, 255*Game.Brightness/100, 255*Game.Brightness/100), pygame.Rect(Temp.Left, Temp.Top, Temp.Right-Temp.Left, Temp.Bottom-Temp.Top), 1)
    else:
        pygame.draw.rect(Game.screen, (255*Game.Brightness/100, 255*Game.Brightness/100, 255*Game.Brightness/100), pygame.Rect(Temp.Left, Temp.Top, Temp.Right-Temp.Left, Temp.Bottom-Temp.Top), 1)

def DrawCircle3D(X, Y, Z, radius, draw, color=None):
    if (color == None): color = (255,255,255)
    r = GetProjectedX(X+radius, Y, Z)-GetProjectedX(X, Y, Z)
    if r < 1:
        return
    pygame.draw.circle(Game.screen, 
        (color[0]*Game.Brightness/100, color[1]*Game.Brightness/100, color[2]*Game.Brightness/100), 
        (GetProjectedX( X, Y, Z ), GetProjectedY( X, Y, Z )), r, 1)

def DrawEllipse3D(X, Y, Z, radiusX, radiusY, draw, color=None):
    if (color == None): color = (255,255,255)
    w = radiusX*256/2/max(1,Z)
    h = radiusY*256/2/max(1,Z)
    pygame.draw.ellipse(Game.screen, 
        (color[0]*Game.Brightness/100, color[1]*Game.Brightness/100, color[2]*Game.Brightness/100), 
        pygame.Rect(GetProjectedX( X, Y, Z )-w, GetProjectedY( X, Y, Z )-h, max(2,w*2), max(2,h*2)), 1) 

def DrawFilledRect3D(Rect, Depth, draw):
    Temp = RectType()
    
    Temp.Left = GetProjectedX( Rect.Top, Rect.Left, Depth ) + 1
    Temp.Top = GetProjectedY( Rect.Top, Rect.Left, Depth ) + 1
    Temp.Right = GetProjectedX( Rect.Right, Rect.Bottom, Depth ) - 1
    Temp.Bottom = GetProjectedY( Rect.Right, Rect.Bottom, Depth ) - 1

    if ( draw ):
        pygame.draw.rect(Game.screen, (255*Game.Brightness/100, 255*Game.Brightness/100, 255*Game.Brightness/100), pygame.Rect(Temp.Left, Temp.Top, Temp.Right-Temp.Left, Temp.Bottom-Temp.Top))
    else:
        pygame.draw.rect(Game.screen, (0, 0, 0), pygame.Rect(Temp.Left, Temp.Top, Temp.Right-Temp.Left, Temp.Bottom-Temp.Top))

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
    DrawCircle3D(Ball.Pos.X, Ball.Pos.Y, Ball.Pos.Z, Game.Stage.BallSize, draw)

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
    elif CollisionType == 3:
        Game.Player1PaddleWav.play()    
    elif CollisionType == 4:
        Game.Player2PaddleWav.play()    
    elif CollisionType == 5:
        Game.WallWav.play() 
        
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
    if Player == 0:
        for j in range(0, 5):
            Points = []
            for p in Game.XPoints:
                Points.append((p[0]*20-10+Pos[0]+j*30, p[1]*20-10+Pos[1]))
            pygame.draw.polygon(Game.screen, Color, Points, j >= Score)
    else:
        for j in range(0, 5):
            pygame.draw.circle(Game.screen, Color, (Pos[0] + j*30, Pos[1]), 10, j >= Score)

def DrawTextCentered(Pos, Text, Color):
    TextSurface = Game.font.render(Text, 1, Color)
    TextPos = TextSurface.get_rect(centerx=Pos[0], centery=Pos[1])
    Game.screen.blit(TextSurface, TextPos)

def DrawGame():
    DrawStage( Game.Stage, 1 )
    DrawPaddle( Game.Paddle1, Game.Stage, 1 )
    DrawPaddle( Game.Paddle2, Game.Stage, 1 )
    DrawBall( Game.Ball, Game.Stage, 1 )

    v = 255*Game.Brightness/100
    color = (v, v, v)

    DrawScoreBar((200, 20), Game.Paddle1.Score, color, 0)
    DrawScoreBar((850, 20), Game.Paddle2.Score, color, 1)

    DrawTextCentered((Game.screen.get_width()/2, 20), "Stage %d" % (Game.CurLevel+1), color)

def DrawScoreEffect():
    RingSpacing = 8*256
    RingSpeed = 3*256
    NumRings = 10
    NumSteps = 20
    clock = pygame.time.Clock()
    Game.ScoreWav.play()
    for step in range(1, NumSteps):
        pygame.draw.rect(Game.screen, (0, 0, 0), pygame.Rect(0, 0, Game.screen.get_width(), Game.screen.get_height()))
        b = 255*(1.0-float(step)/NumSteps)
        DrawCircle3D(Game.Ball.LastPos.X+Game.Ball.LastVel.X*step/2, Game.Ball.LastPos.Y+Game.Ball.LastVel.Y*step/2, Game.Ball.LastPos.Z+Game.Ball.LastVel.Z*step/2, Game.Stage.BallSize, True, (b,b,b))
        random.seed(12345678)
        for ring in range(0, NumRings):
            b = 255*(1.0-float(step)/NumSteps)*(0.5+0.5*math.cos(math.pi*float(ring)/NumRings))
            DrawCircle3D(Game.Ball.LastPos.X+Game.Ball.LastVel.X*ring, Game.Ball.LastPos.Y+Game.Ball.LastVel.Y*ring, Game.Ball.LastPos.Z+Game.Ball.LastVel.Z*ring, (-ring+1)*RingSpacing + RingSpeed*step, True, (b, b, b))
        DrawGame()
        pygame.display.flip()
        clock.tick(20)

def SequenceIntro():
    text = Game.font.render("3 d   p o n g", 1, (255*Game.Timer0/100, 255*Game.Timer0/100, 255*Game.Timer0/100))
    Game.screen.blit(text, text.get_rect(centerx=Game.screen.get_width()/2, centery=Game.screen.get_height()/2))
    if (Game.Timer1 == 0):
        Game.Brightness = 0
        Game.Timer0 += 1
        if (Game.Timer0 >= 100):
            Game.Timer1 = 1
    elif (Game.Timer1 == 1):
        if (Game.Brightness < 100): Game.Brightness += 1
        Game.Timer0 -= 2
        if (Game.Timer0 <= 0):
            Game.IntroWav.play()
            Game.Sequence = 2
            Game.Timer0 = 0
            Game.Timer1 = 0
        DrawGame()

def SequenceNewStage():
    text = Game.font.render(StageDescs[Game.CurLevel]['Name'], 1, (255*Game.Timer0/100, 255*Game.Timer0/100, 255*Game.Timer0/100))
    Game.screen.blit(text, text.get_rect(centerx=Game.screen.get_width()/2, centery=Game.screen.get_height()/2))
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
            Game.IntroWav.play()
            Game.Sequence = 2
            Game.Timer0 = 0
            Game.Timer1 = 0
    DrawGame()

def SequenceBallRelease():
    if (Game.Brightness < 100): Game.Brightness += 1
    v = math.sin(3.14159*Game.Timer0/30)
    text = Game.font.render(str(3-Game.Timer1), 1, (255*v, 255*v, 255*v))
    Game.screen.blit(text, text.get_rect(centerx=Game.screen.get_width()/2, centery=Game.screen.get_height()/2))
    Game.Timer0 += 1
    if (Game.Timer0 > 25):
        Game.Timer1 += 1
        Game.Timer0 = 0
    if (Game.Timer1 >= 3):
        Game.Sequence = 3
        Game.EndTimeout = 0
    DrawGame()

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
    text = Game.font.render("; - {", 1, (255*Game.Timer0/100, 255*Game.Timer0/100, 255*Game.Timer0/100))
    Game.screen.blit(text, text.get_rect(centerx=Game.screen.get_width()/2, centery=Game.screen.get_height()/2))
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
    DrawGame()

def SequenceYouWin():
    StartY = 250
    TotalScore = 0
    for i in range(0, len(StageDescs)):
        v = clamp(255*Game.Timer0/60 - i*60, 0, 255)
        color = (v, v, v)
        minus = Game.font.render("-", 1, color)
        equals = Game.font.render("=", 1, color)
    
        text = Game.font.render(StageDescs[i]['Name'], 1, color)
        Game.screen.blit(text, text.get_rect(centerx=125, centery=StartY + i*50))

        PlayerScore = StageDescs[i]['PlayerScore']
        AIScore = StageDescs[i]['AIScore']
        DiffScore = PlayerScore - AIScore

        DrawScoreBar((250, StartY + i*50), PlayerScore, color, 0)
        Game.screen.blit(minus, (text.get_rect(centerx=475, centery=StartY + i*50)))
        DrawScoreBar((550, StartY + i*50), AIScore, color, 1)
        Game.screen.blit(equals, (text.get_rect(centerx=775, centery=StartY + i*50)))
        DrawScoreBar((850, StartY + i*50), DiffScore, color, 0)

        TotalScore += DiffScore

    pygame.draw.line(Game.screen, color, (250, StartY + len(StageDescs)*50), (950, StartY + len(StageDescs)*50), 1)
    #Game.screen.blit(equals, (text.get_rect(centerx=800, centery=StartY + i*50)))
    x = 250
    y = StartY + (len(StageDescs)+1)*50
    for j in range(0, 5*len(StageDescs)):
        Points = []
        for p in Game.XPoints:
            Points.append((p[0]*20-10+x, p[1]*20-10+y))
        pygame.draw.polygon(Game.screen, color, Points, j >= TotalScore)
        #pygame.draw.circle(Game.screen, color, (x, y), 10, j >= TotalScore)
        x += 30
        if (x > 980):
            x = 250
            y += 50

    if (TotalScore >= 5*len(StageDescs)):
        text = Game.font.render("; - D", 1, color)
    elif (TotalScore >= 4*len(StageDescs)):
        text = Game.font.render("; - >", 1, color)
    elif (TotalScore >= 3*len(StageDescs)):
        text = Game.font.render("; - )", 1, color)
    elif (TotalScore >= 2*len(StageDescs)):
        text = Game.font.render("; - }", 1, color)
    else: #(TotalScore >= 1*len(StageDescs)):
        text = Game.font.render("; - |", 1, color)
    Game.screen.blit(text, text.get_rect(centerx=Game.screen.get_width()/2, centery=150))

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

def main():
    size = (1200,825)
    if olpcgames.ACTIVITY:
        size = olpcgames.ACTIVITY.game_size

    pygame.init()

    # Graphics init
    Game.screen = pygame.display.set_mode(size)
    Game.font = pygame.font.Font(None, 36)
    pygame.display.set_caption('GameJam test')
    pygame.mouse.set_visible(0)

    # Sound assets
    Game.IntroWav = pygame.mixer.Sound('sound/intro.wav')
    Game.ScoreWav = pygame.mixer.Sound('sound/score.wav')
    Game.Player1PaddleWav = pygame.mixer.Sound('sound/player1paddle.wav')
    Game.Player2PaddleWav = pygame.mixer.Sound('sound/player2paddle.wav')
    Game.WallWav = pygame.mixer.Sound('sound/wall.wav')

    clock = pygame.time.Clock()

    NewGame()
    
    running = True
    while running:
        # Aim for 20fps.
        clock.tick(20)

        # Process events.
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == KEYDOWN and event.key == K_ESCAPE:
                return
            # Cheat code for testing.
            #elif event.type    == KEYDOWN and event.key == K_UP:
            #   if (Game.Paddle1.Score < 5):
            #       Game.Paddle1.Score += 1
            elif event.type == MOUSEBUTTONDOWN:
                Game.MouseDown = 1
            elif event.type == MOUSEBUTTONUP:
                Game.MouseDown = 0
            elif event.type == MOUSEMOTION:
                Game.MouseX = event.pos[0]
                Game.MouseY = event.pos[1]

        # Clear the screen.
        pygame.draw.rect(Game.screen, (0, 0, 0), pygame.Rect(0, 0, Game.screen.get_width(), Game.screen.get_height()))

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

        pygame.display.flip()
        
if __name__ == "__main__":
    logging.basicConfig()
    main()


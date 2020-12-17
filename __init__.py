# -*- coding: utf-8 -*-
################################################################################

from modules.core.props import Property, StepProperty
from modules.core.step import StepBase
from modules import cbpi
import time
import os

LOG_DIR = "./logs/"
APP_LOG = "app.log"
LOG_SEP = "-=-"

################################################################################
@cbpi.step
class SimpleManualStep(StepBase):
    # Properties
    heading = Property.Text("Heading", configurable=True, default_value="Step Alert", description="First line of notification.")
    message = Property.Text("Message", configurable=True, default_value="Press next button to continue", description="Second line of notification.")
    notifyType = Property.Select("Type", options=["success","info","warning","danger"])
    proceed = Property.Select("Next Step", options=["Pause","Continue"], description="Whether or not to automatically continue to the next brew step.")

    #-------------------------------------------------------------------------------
    def init(self):
        if self.notifyType not in ["success","info","warning","danger"]:
            self.notifyType = "info"
        self.notify(self.heading, self.message, type=self.notifyType, timeout=None)
        if self.proceed == "Continue":
            next(self)

################################################################################
@cbpi.step
class SimpleTargetStep(StepBase):
    # Properties
    auto_mode = Property.Select("Auto Mode", options=["Set to ON","Set to OFF","No Change"])
    kettle = StepProperty.Kettle("Kettle")
    target = Property.Number("Target Temp", configurable=True)

    #-------------------------------------------------------------------------------
    def init(self):
        self.set_target_temp(float(self.target), int(self.kettle))
        if self.auto_mode == "Set to ON":
            self.setAutoMode(True)
        elif self.auto_mode == "Set to OFF":
            self.setAutoMode(False)
        next(self)

    #-------------------------------------------------------------------------------
    def setAutoMode(self, auto_state):
        try:
            kettle = cbpi.cache.get("kettle")[int(self.kettle)]
            if (kettle.state is False) and (auto_state is True):
                # turn on
                if kettle.logic is not None:
                    cfg = kettle.config.copy()
                    cfg.update(dict(api=cbpi, kettle_id=kettle.id, heater=kettle.heater, sensor=kettle.sensor))
                    instance = cbpi.get_controller(kettle.logic).get("class")(**cfg)
                    instance.init()
                    kettle.instance = instance
                    def run(instance):
                        instance.run()
                    t = cbpi.socketio.start_background_task(target=run, instance=instance)
                kettle.state = not kettle.state
                cbpi.emit("UPDATE_KETTLE", cbpi.cache.get("kettle")[int(self.kettle)])
            elif (kettle.state is True) and (auto_state is False):
                # turn off
                kettle.instance.stop()
                kettle.state = not kettle.state
                cbpi.emit("UPDATE_KETTLE", cbpi.cache.get("kettle")[int(self.kettle)])
        except Exception as e:
            cbpi.notify("Error", "Failed to set Auto mode {}".format(["OFF","ON"][auto_state]), type="danger", timeout=None)
            cbpi.app.logger.error(e)

################################################################################
@cbpi.step
class SimpleActorTimer(StepBase):
    # Properties
    actor1 = StepProperty.Actor("Actor 1")
    actor2 = StepProperty.Actor("Actor 2")
    timer = Property.Number("Timer in Minutes", configurable=True, description="Timer is started immediately.")

    #-------------------------------------------------------------------------------
    def init(self):
        self.actors = [self.actor1, self.actor2]
        self.actors_on()

    #-------------------------------------------------------------------------------
    def finish(self):
        self.actors_off()

    #-------------------------------------------------------------------------------
    def execute(self):
        # Check if Timer is Running
        if self.is_timer_finished() is None:
            self.start_timer(float(self.timer) * 60)

        # Check if timer finished and go to next step
        if self.is_timer_finished() == True:
            self.notify("{} complete".format(self.name), "Starting the next step", timeout=None)
            next(self)

    #-------------------------------------------------------------------------------
    def actors_on(self):
        for actor in self.actors:
            try: self.actor_on(int(actor))
            except: pass

    def actors_off(self):
        for actor in self.actors:
            try: self.actor_off(int(actor))
            except: pass

################################################################################
@cbpi.step
class SimpleChillToTemp(StepBase):
    # Properties
    actor1 = StepProperty.Actor("Actor 1", description="Actor to turn on until target temp is reached")
    actor2 = StepProperty.Actor("Actor 2", description="Actor to turn on until target temp is reached")
    kettle_prop = StepProperty.Kettle("Kettle", description="Kettle in which the chilling takes place")
    target_prop = Property.Number("Temperature", configurable=True, description="Target temperature of chill step")

    #-------------------------------------------------------------------------------
    def init(self):
        self.actors = [self.actor1, self.actor2]
        self.target = float(self.target_prop)
        self.kettle = int(self.kettle_prop)

        # set target temp
        if self.kettle:
            self.set_target_temp(self.target, self.kettle)
            self.start_time = time.time()
            self.actors_on()
        else:
            cbpi.notify("No kettle defined", "Starting the next step", type="danger", timeout=None)
            next(self)

    #-------------------------------------------------------------------------------
    def reset(self):
        self.set_target_temp(self.target, self.kettle)

    #-------------------------------------------------------------------------------
    def finish(self):
        self.actors_off()

    #-------------------------------------------------------------------------------
    def execute(self):
        # Check if Target Temp is reached
        if float(self.get_kettle_temp(self.kettle)) <= self.target:
            elapsed_time = int(time.time() - self.start_time)
            hours, remainder = divmod(elapsed_time, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours:
                elapsed_text = '{}:{:0>2d}:{:0>2d}'.format(hours, minutes, seconds)
            else:
                elapsed_text = '{}:{:0>2d}'.format(minutes, seconds)

            self.notify("{} complete".format(self.name), "Chill temp reached in {}".format(elapsed_text), timeout=None)
            next(self)

    #-------------------------------------------------------------------------------
    def actors_on(self):
        for actor in self.actors:
            try: self.actor_on(int(actor))
            except: pass

    def actors_off(self):
        for actor in self.actors:
            try: self.actor_off(int(actor))
            except: pass

################################################################################
@cbpi.step
class SimpleClearLogsStep(StepBase):
    #-------------------------------------------------------------------------------
    delete_finished = False

    def init(self):
        log_names = os.listdir(LOG_DIR)
        for log_name in log_names:
            if (log_name[-4:] == ".log") and (log_name != APP_LOG) and (LOG_SEP not in log_name):
                if os.path.isfile(LOG_DIR+log_name):
                    os.remove(LOG_DIR+log_name)
        self.delete_finished = True

    def start(self):
        pass

    def reset(self):
        pass

    def finish(self):
        pass

    def execute(self):
        pass

        # Check if timer finished and go to next step
        if self.delete_finished == True:
            self.notify("Logfiles Deleted!" , "Starting the next step")
            next(self)

################################################################################
@cbpi.step
class SimpleSaveLogsStep(StepBase):

    #-------------------------------------------------------------------------------
    def execute(self):
        brew_name  = cbpi.get_config_parameter("brew_name", "")
        if brew_name:
            brew_name = "_".join(brew_name.split())
            brew_name = brew_name + time.strftime("_%Y_%m_%d")
        else:
            brew_name = time.strftime("Brew_%Y_%m_%d")
        brew_name = brew_name.replace('%','')
        brew_name = brew_name.replace("#","")
        brew_name = brew_name.replace("'","")
        brew_name = brew_name.replace("$","")
        brew_name = brew_name.replace("´","")
        
        log_names = os.listdir(LOG_DIR)
        for log_name in log_names:
            if (log_name[-4:] == ".log") and (log_name != APP_LOG) and (LOG_SEP not in log_name):
                if os.path.isfile(LOG_DIR+log_name):
                    os.system("cp {} {}".format(LOG_DIR+log_name, LOG_DIR+brew_name+LOG_SEP+log_name))

        self.notify("Logfiles Saved!" , "Name: %s Starting the next step" % brew_name)
        next(self)

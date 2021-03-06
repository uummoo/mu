"""midiplug helps generating midifiles for particular synthesizer."""

from mu.mel.abstract import AbstractPitch
from mu.mel import mel
from mu.sco import old
from mu.utils import infit
from mu.utils import interpolations
from mu.utils import tools

import abc
import bisect
import functools
import itertools
import logging
import numbers
import operator
import os
import subprocess

import mido

__directory = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(__directory, "", "../mel/12edo"), "r") as f:
    _12edo_freq = tuple(float(line[:-1]) for line in f.readlines())


# TODO(Add proper documentation)
# TODO(write expected types in methods arguments)


class MidiTone(old.Tone):
    _init_args = {}

    def __init__(self, *args, tuning: tuple = tuple([]), **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if tuning:
            self.tuning = tuple(tuning)
        else:
            self.tuning = tuple([])

    def make_control_message(
        self, arg: str, value: float, channel: int
    ) -> mido.Message:
        """Make one control message object."""

        boundaries, control_number = self._init_args[arg]
        difference = boundaries[1] - boundaries[0]
        normalized = value - boundaries[0]
        percent = normalized / difference
        value = int(127 * percent)
        return mido.Message(
            "control_change",
            time=0,
            control=control_number,
            value=value,
            channel=channel,
        )

    def control_messages(self, channel: int, n_points: int) -> list:
        """Generate control messages for a particular tone.

        Since tones can be distributed on different midi channels, the respective
        channel has to be submitted. Furthermore the function needs to know how many
        points the tone lasts in the respective grid for control messages that
        dynamically change within the tone.

        Return list of lists where each sublist represents one tick. Each
        tick contains control messages that are supposed to get send at this
        particular tick.
        """

        messages_per_tick = [[] for i in range(n_points)]

        for arg in self._init_args:

            value = getattr(self, arg)
            typv = type(value)

            if value is not None:

                if isinstance(value, numbers.Real):
                    messages_per_tick[0].append(
                        self.make_control_message(arg, value, channel)
                    )

                elif isinstance(value, infit.InfIt):
                    for n in range(n_points):
                        local_value = next(value)
                        if local_value is not None:
                            messages_per_tick[n].append(
                                self.make_control_message(arg, local_value, channel)
                            )

                elif isinstance(value, interpolations.InterpolationLine):

                    for n, local_value in enumerate(
                        value(n_points, interpolation_type="points")
                    ):
                        messages_per_tick[n].append(
                            self.make_control_message(arg, local_value, channel)
                        )

                else:
                    msg = "Unknown type '{}' of value '{}' for argument '{}'.".format(
                        typv, value, arg
                    )
                    raise NotImplementedError(msg)

        return list(list(tick) for tick in messages_per_tick)


class _SynthesizerMidiTone(abc.ABCMeta):
    """Metaclass for Tone - objects that are intented to generate midi output."""

    tone_args = (
        "pitch",
        "delay",
        "duration",
        "volume",
        "glissando",
        "vibrato",
        "tuning",
    )

    def __new__(cls, name, bases, attrs):
        def auto_init(self, *args, **kwargs):
            arg_names = cls.tone_args + tuple(self._init_args.keys())
            length_tone_args = len(cls.tone_args)
            length_args = len(args)

            for counter, arg_val, arg_name in zip(range(length_args), args, arg_names):
                if counter > length_tone_args:
                    tolerance = self.__init_args[arg_name][0]
                    try:
                        assert arg_val <= tolerance[0]
                        assert arg_val >= tolerance[1]
                    except AssertionError:
                        msg = "The value for '{0}' has to be >= {1} and <= {2}.".format(
                            arg_name, tolerance[0], tolerance[1]
                        )
                        raise ValueError(msg)

                    setattr(self, arg_name, arg_val)

            for arg_name in arg_names[length_args:]:
                if arg_name not in kwargs.keys() and arg_name not in cls.tone_args:
                    kwargs.update({arg_name: None})

            self.__dict__.update(kwargs)

            args = args[: len(cls.tone_args)]
            kwargs = {arg: kwargs[arg] for arg in kwargs if arg in cls.tone_args}

            MidiTone.__init__(self, *args, **kwargs)

        attrs["__init__"] = auto_init
        return super(_SynthesizerMidiTone, cls).__new__(cls, name, bases, attrs)


class PyteqTone(MidiTone, metaclass=_SynthesizerMidiTone):
    """Tone object to work with Pianoteq"""

    _init_args = {
        "unison_width": ((0, 20), 2),
        "hammer_noise": ((0.20, 3), 3),
        "diapason": ((220, 880), 5),
        "octave_stretching": ((0.95, 3), 6),
        "unison_balance": ((-1, 1), 7),
        "direct_sound_duration": ((0, 5), 8),
        "hammer_hard_piano": ((0, 2), 9),
        "spectrum_profile_1": ((-15, 15), 10),
        "spectrum_profile_2": ((-15, 15), 11),
        "spectrum_profile_3": ((-15, 15), 12),
        "spectrum_profile_4": ((-15, 15), 13),
        "spectrum_profile_5": ((-15, 15), 14),
        "spectrum_profile_6": ((-15, 15), 15),
        "spectrum_profile_7": ((-15, 15), 16),
        "spectrum_profile_8": ((-15, 15), 17),
        "strike_point": ((1 / 64, 1 / 2), 18),
        "pinch_harmonic_point": ((1 / 64, 1 / 2), 19),
        "pickup_symmetry": ((0, 1), 20),
        "pickup_distance": ((0.20, 2), 21),
        "soft_level": ((0, 1), 22),
        "impedance": ((0.3, 3), 23),
        "cutoff": ((0.3, 3), 24),
        "q_factor": ((0.2, 5), 25),
        "string_length": ((0.8, 10), 26),
        "sympathetic_resonance": ((0, 5), 27),
        "duplex_scale_resonance": ((0, 20), 28),
        "quadratic_effect": ((0, 20), 29),
        "damper_noise": ((-85, 12), 30),
        "damper_position": ((1 / 64, 1 / 2), 31),
        "last_damper": ((0, 128), 32),
        "pedal_noise": ((-70, 25), 33),
        "key_release_noise": ((-70, 25), 34),
        "damping_duration": ((0.03, 10), 35),
        "mute": ((0, 1), 36),
        "clavinet_low_mic": ((-1, 1), 37),
        "clavinet_high_mic": ((-1, 1), 38),
        "equalizer_switch": ((0, 1), 39),
        "hammer_tine_nose": ((-100, 25), 40),
        "blooming_energy": ((0, 2), 41),
        "blooming_inertia": ((0.10, 3), 42),
        "aftertouch": ((0, 1), 43),
        "post_effect_gain": ((-12, 12), 44),
        "bounce_switch": ((0, 1), 45),
        "bounce_delay": ((10, 250), 46),
        "bounce_sync": ((0, 1), 47),
        "bounce_sync_speed": ((16, 1 / 8), 48),
        "bounce_velocity_speed": ((0, 100), 49),
        "bounce_delay_loss": ((0, 100), 50),
        "bounce_velocity_loss": ((0, 100), 51),
        "bounce_humanization": ((0, 100), 52),
        "sustain_pedal": ((0, 1), 53),
        "soft_pedal": ((0, 1), 54),
        "sostenuto_pedal": ((0, 1), 55),
        "harmonic_pedal": ((0, 1), 56),
        "rattle_pedal": ((0, 1), 57),
        "buff_stop_pedal": ((0, 1), 58),
        "celeste_pedal": ((0, 1), 59),
        "super_sostenuto": ((0, 1), 60),
        "pinch_harmonic_pedal": ((0, 1), 61),
        "glissando_pedal": ((0, 1), 62),
        "harpsichord_register_1": ((0, 1), 63),
        "harpsichord_register_2": ((0, 1), 64),
        "harpsichord_register_3": ((0, 1), 65),
        "reversed_sustain": ((0, 1), 66),
        "mozart_rail": ((0, 1), 67),
        "pedal_1": ((0, 1), 68),
        "pedal_2": ((0, 1), 69),
        "pedal_3": ((0, 1), 70),
        "pedal_4": ((0, 1), 71),
        "stereo_width": ((0, 5), 72),
        "lid_position": ((0, 1), 73),
        "output_mode": ((0, 3), 74),
        "mic_level_compensation": ((0, 1), 75),
        "mic_delay_compensation": ((0, 1), 76),
        "head_x_position": ((-10, 10), 77),
        "head_y_position": ((-6, 6), 78),
        "head_z_position": ((0, 3.5), 79),
        "head_diameter": ((10, 50), 80),
        "head_angle": ((-180, 180), 81),
        "mic_1_mic_switch": ((0, 1), 82),
        "mic_1_x_position": ((-10, 10), 83),
        "mic_1_y_position": ((-6, 6), 84),
        "mic_1_z_position": ((0, 3.5), 85),
        "mic_1_azimuth": ((-180, 180), 86),
        "mic_1_elevation": ((-180, 180), 87),
        "mic_1_level_1": ((-85, 6), 90),
        "reverb_switch": ((0, 1), 91),
        "sound_speed": ((200, 500), 92),
        "wall_distance": ((0, 6), 93),
        "hammer_hard_mezzo": ((0, 2), 94),
        "hammer_hard_forte": ((0, 2), 95),
        "effect1_switch": ((0, 1), 102),
        "effect1_param1": ((0, 1), 103),
        "effect1_param2": ((0, 1), 104),
        "effect1_param3": ((0, 1), 105),
        "effect1_param4": ((0, 1), 106),
        "effect1_param5": ((0, 1), 107),
        "effect1_param6": ((0, 1), 108),
        "effect1_param7": ((0, 1), 109),
        "effect1_param8": ((0, 1), 110),
        "mic_2_x_position": ((-10, 10), 111),
        "mic_2_y_position": ((-6, 6), 112),
        "mic_2_z_position": ((0, 3.5), 113),
        "mic_2_azimuth": ((-180, 180), 114),
        "mic_2_elevation": ((-180, 180), 115),
        "mic_2_mic_switch": ((0, 1), 116),
    }


class DivaTone(MidiTone, metaclass=_SynthesizerMidiTone):
    """Tone object to work with U-He Diva."""

    # control value 2 in voice 1 is already used for fine_tune_cents
    # (making sure the right pitch get played)
    # _init_args = {"fine_tune_cents": ((-100, 100), 2)}

    _init_args = {
        "volume_curve": ((0, 1), 3),
        "vcf1_feedback": ((0, 100), 4),
        "vcf1_filter_fm": ((-24, 24), 7),
        "vcf1_freq_mod_depth": ((-120, 120), 12),
        "vcf1_freq_mod_depth2": ((-120, 120), 10),
        "vcf1_cutoff_frequency": ((30, 150), 14),
        "vcf1_resonance": ((0, 100), 17),
        "lfo2_delay": ((0, 100), 20),
        "lfo2_depth_mod": ((0, 100), 21),
        "lfo2_freq_mod": ((0, 100), 23),
        "lfo2_phase": ((0, 100), 24),
        "lfo2_rate": ((-5, 5), 25),
        "osc_vibrato": ((0, 100), 26),
        # mixing between different osciallators (50 means both same level, while
        # with 0 only the first osciallator can be heard)
        "osc_mix": ((0, 100), 27),
        "osc_fm": ((0, 100), 28),
        "osc_noise_volume": ((0, 100), 29),
        "osc_tune_mod_depth1": ((-24, 24), 33),
        "osc_tune_mod_depth2": ((-24, 24), 32),
    }

    def control_messages(self, channel: int, n_points: int, midi_key: int) -> tuple:
        messages_per_tick = super().control_messages(channel, n_points)
        cent_deviation = AbstractPitch.ratio2ct(self.pitch.freq / _12edo_freq[midi_key])
        assert cent_deviation > -100 and cent_deviation < 100
        percentage = (cent_deviation + 100) / 200
        value = int(percentage * 127)
        messages_per_tick[0].append(
            mido.Message("control_change", time=0, control=2, value=value, channel=0)
        )
        return messages_per_tick


class SimpleMidiFile(object):
    ticks_per_second = 1000
    tick_size = 1 / ticks_per_second
    maximum_cent_deviation = 200  # up and down; total range is 400 ct
    total_range_cent_deviation = maximum_cent_deviation * 2
    maximum_pitch_bending = 16382
    maximum_pitch_bending_positive = 8191
    pb_warn = "Maximum pitch bending is {} cents up or down!".format(
        maximum_pitch_bending
    )
    note_on_msg_delay = 20
    pitch_msg_delay = 1

    # there are 16 midi channels
    available_channel = tuple(i for i in range(16))
    # available_midi_notes = tuple(range(128))

    def __init__(self, sequence: tuple) -> None:
        self._sequence = sequence
        self._midi_file = self._convert2midi_file(sequence)

    def _get_velocity(self, tone: old.Tone) -> int:
        if tone.volume is not None:
            typv = type(tone.volume)

            if isinstance(tone.volume, numbers.Real):
                volume = float(tone.volume)

            elif isinstance(tone.volume, infit.InfIt):
                volume = next(tone.volume)
                try:
                    assert isinstance(volume, numbers.Real)
                except AssertionError:
                    msg = "infit.InfIt object return bad type '{}'".format(type(volume))
                    msg += " when trying to find a value for "
                    msg += "the volume argument."
                    raise ValueError(msg)

            elif typv is interpolations.InterpolationLine:
                volume = tone.volume(3, interpolation_type="points")[0]

            else:
                msg = "Unknown type '{}' for volume ".format(typv)
                msg += "argument with the value '{}'".format(tone.volume)
                raise NotImplementedError(msg)

            velocity = int((volume / 1) * 127)
        else:
            velocity = 64

        return velocity

    def _convert_seconds2ticks(self, duration: float) -> int:
        return int(duration // self.tick_size)

    def _make_messages_for_one_tone(self, tone: old.Tone, channel_number: int) -> tuple:
        freq = tone.pitch.freq
        key = tools.find_closest_index(freq, _12edo_freq)
        cent_deviation = mel.SimplePitch.hz2ct(_12edo_freq[key], freq)

        if cent_deviation != 0:
            pitch_percent = (
                cent_deviation + self.maximum_cent_deviation
            ) / self.total_range_cent_deviation

            if pitch_percent > 1:
                pitch_percent = 1
                logging.warn(self.pb_warn)

            if pitch_percent < 0:
                pitch_percent = 0
                logging.warn(self.pb_warn)

            midi_pitch = int(self.maximum_pitch_bending * pitch_percent)
            midi_pitch -= self.maximum_pitch_bending_positive

        else:
            midi_pitch = self.maximum_pitch_bending_positive

        # time=18: adding small delay for avoiding pitch-bending effects

        messages = []
        messages.append(
            mido.Message(
                "pitchwheel",
                channel=channel_number,
                pitch=midi_pitch,
                time=self.pitch_msg_delay,
            )
        )

        velocity = self._get_velocity(tone)
        duration = (
            self._convert_seconds2ticks(tone.duration)
            - self.note_on_msg_delay
            - self.pitch_msg_delay
        )

        messages.append(
            mido.Message(
                "note_on",
                note=key,
                velocity=velocity,
                time=self.note_on_msg_delay,
                channel=channel_number,
            )
        )

        for n in range(duration - 1):
            messages.append(
                mido.Message(
                    "pitchwheel", channel=channel_number, pitch=midi_pitch, time=1
                )
            )

        messages.append(
            mido.Message(
                "note_off", note=key, velocity=velocity, time=1, channel=channel_number
            )
        )

        return tuple(messages)

    def _make_empty_msg(self, tone: old.Tone) -> mido.Message:
        return mido.Message("sysex", time=self._convert_seconds2ticks(tone.duration),)

    def _make_messages(self, sequence: tuple) -> tuple:
        messages = []

        channel_cycle = infit.Cycle(self.available_channel)
        for tone in sequence:
            if tone.pitch.is_empty:
                messages.append(self._make_empty_msg(tone))
            else:
                messages.extend(
                    self._make_messages_for_one_tone(tone, next(channel_cycle))
                )

        return tuple(messages)

    def _convert2midi_file(self, sequence: tuple) -> mido.MidiFile:
        messages = self._make_messages(sequence)
        midi_file = self._mk_midi_file(messages)
        return midi_file

    def _mk_midi_file(self, messages: tuple) -> mido.MidiFile:
        mid = mido.MidiFile(type=0)
        bpm = 120
        ticks_per_minute = self.ticks_per_second * 60
        ticks_per_beat = int(ticks_per_minute / bpm)
        mid.ticks_per_beat = ticks_per_beat
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage("instrument_name", name="Acoustic Grand Piano"))

        for i in self.available_channel:
            track.append(mido.Message("program_change", program=0, time=0, channel=i))

        for message in messages:
            track.append(message)

        return mid

    def __repr__(self) -> str:
        return "SimpleMidiFile({})".format(self._sequence)

    def export(self, name: str = "test.mid") -> None:
        """save content of object to midi-file."""
        self._midi_file.save(name)


class MidiFile(abc.ABC):
    maximum_cent_deviation = 1200  # up and down; total range is 2400 ct
    maximum_pitch_bending = 16382
    maximum_pitch_bending_positive = 8191
    ticks_per_second = 1000
    grid_size = 1 / ticks_per_second

    delay_between_control_messages_and_note_on_message = 0

    # there are 16 midi channels
    available_channel = tuple(i for i in range(16))

    def __init__(
        self,
        sequence: tuple,
        available_midi_notes: tuple = tuple(range(128)),
        tie: bool = False,
    ):
        self.__available_midi_notes = available_midi_notes
        if tie:
            sequence = MidiFile.discard_pauses_and_tie_sequence(tuple(sequence))
        else:
            sequence = tuple(sequence)
        filtered_sequence = tuple(t for t in sequence if not t.pitch.is_empty)
        gridsize = self.grid_size
        self.__duration = float(sum(t.delay for t in sequence))
        n_hits = int(self.__duration // gridsize)
        n_hits += self.delay_between_control_messages_and_note_on_message + 2
        self.__grid = tuple(i * gridsize for i in range(0, n_hits))
        self.__gridsize = gridsize
        self.__grid_position_per_tone = self.detect_grid_position(
            sequence, self.__grid, self.__duration
        )
        self.__amount_available_midi_notes = len(available_midi_notes)
        self.__sequence = sequence
        self.__overlapping_dict = MidiFile.mk_overlapping_dict(filtered_sequence)
        self.__midi_keys_dict = MidiFile.mk_midi_key_dictionary(
            set(t.pitch for t in filtered_sequence),
            available_midi_notes,
            self.__amount_available_midi_notes,
        )
        self.keys = MidiFile.distribute_tones_on_midi_keys(
            filtered_sequence,
            self.__amount_available_midi_notes,
            available_midi_notes,
            self.__overlapping_dict,
            self.__midi_keys_dict,
        )
        pitch_data = MidiFile.mk_pitch_sequence(filtered_sequence)
        self.__pitch_sequence = pitch_data[0]
        self.__tuning_sequence = pitch_data[1]
        self.__midi_pitch_dictionary = pitch_data[2]

        n_points_per_tone = tuple(b - a for a, b in self.__grid_position_per_tone)
        self.__control_messages = self.mk_control_messages_per_tone(
            filtered_sequence, n_points_per_tone
        )

        self.__note_on_off_messages = self.mk_note_on_off_messages(
            filtered_sequence, self.keys
        )
        self.__pitch_bending_per_tone = self.detect_pitch_bending_per_tone(
            filtered_sequence, self.__gridsize, self.__grid_position_per_tone
        )
        self.__pitch_bending_per_channel = self.distribute_pitch_bends_on_channels(
            self.__pitch_bending_per_tone,
            self.__grid,
            self.__grid_position_per_tone,
            self.__gridsize,
        )
        self.__filtered_sequence = filtered_sequence

    @abc.abstractmethod
    def mk_tuning_messages(
        self, sequence, keys, available_midi_notes, overlapping_dict, midi_pitch_dict
    ) -> tuple:
        raise NotImplementedError

    @staticmethod
    def discard_pauses_and_tie_sequence(sequence):
        """this will change the init sequence!!!"""
        new = []
        first = True
        for event in sequence:
            if first is False and event.pitch == mel.TheEmptyPitch:
                information = event.delay
                new[-1].duration += information
                new[-1].delay += information
            else:
                new.append(event)
            first = False
        return tuple(new)

    def distribute_pitch_bends_on_channels(
        self, pitch_bends_per_tone, grid, grid_position_per_tone, gridsize
    ) -> tuple:
        channels = itertools.cycle(range(len(self.available_channel)))
        pitches_per_channels = list(
            list(0 for j in range(len(grid))) for i in self.available_channel
        )
        for position, pitch_bends in zip(grid_position_per_tone, pitch_bends_per_tone):
            channel = next(channels)
            start = (
                position[0] + self.delay_between_control_messages_and_note_on_message
            )
            end = position[1] + self.delay_between_control_messages_and_note_on_message
            pitches_per_channels[channel][start:end] = pitch_bends

        # transform to pitch_bending midi - messages
        first = True
        pitch_bending_messages = []
        total_range = MidiFile.maximum_cent_deviation * 2
        # total_range = MidiFile.maximum_cent_deviation * 1
        warn = "Maximum pitch bending is {0} cents up or down!".format(
            MidiFile.maximum_pitch_bending
        )
        standardmessage0 = tuple(
            mido.Message("pitchwheel", channel=channel_number, pitch=0, time=0)
            for channel_number in self.available_channel
        )
        standardmessage1 = tuple(
            mido.Message("pitchwheel", channel=channel_number, pitch=0, time=1)
            for channel_number in self.available_channel
        )
        for channel_number, channel in zip(
            reversed(self.available_channel), reversed(pitches_per_channels)
        ):
            pitch_bending_messages_sub_channel = []
            for cent_deviation in channel:
                if first is True:
                    time = 1
                else:
                    time = 0
                if cent_deviation != 0:
                    pitch_percent = (
                        cent_deviation + MidiFile.maximum_cent_deviation
                    ) / total_range
                    if pitch_percent > 1:
                        pitch_percent = 1
                        logging.warn(warn)
                    if pitch_percent < 0:
                        pitch_percent = 0
                        logging.warn(warn)
                    midi_pitch = int(MidiFile.maximum_pitch_bending * pitch_percent)
                    midi_pitch -= MidiFile.maximum_pitch_bending_positive
                    msg = mido.Message(
                        "pitchwheel",
                        channel=channel_number,
                        pitch=midi_pitch,
                        time=time,
                    )
                else:
                    if time == 0:
                        msg = standardmessage0[
                            self.available_channel.index(channel_number)
                        ]
                    else:
                        msg = standardmessage1[
                            self.available_channel.index(channel_number)
                        ]
                pitch_bending_messages_sub_channel.append(msg)
            pitch_bending_messages.append(pitch_bending_messages_sub_channel)
            first = False
        pitch_bending_messages = tuple(reversed(pitch_bending_messages))
        return pitch_bending_messages

    def detect_pitch_bending_per_tone(
        self, sequence, gridsize: float, grid_position_per_tone: tuple
    ) -> tuple:
        """Return tuple filled with tuples that contain cent deviation per step."""

        def mk_interpolation(obj, size):

            if obj:
                obj = list(obj.interpolate(gridsize))
            else:
                obj = []

            while len(obj) > size:
                obj = obj[:-1]

            while len(obj) < size:
                obj.append(0)

            return obj

        pitch_bending = []
        for tone, start_end in zip(sequence, grid_position_per_tone):
            size = start_end[1] - start_end[0]
            glissando = mk_interpolation(tone.glissando, size)
            vibrato = mk_interpolation(tone.vibrato, size)
            resulting_cents = tuple(a + b for a, b in zip(glissando, vibrato))
            pitch_bending.append(resulting_cents)

        return tuple(pitch_bending)

    def mk_note_on_off_messages(self, sequence, keys) -> tuple:
        """Generate Note on / off messages for every tone.

        Resulting tuple has the form:
        ((note_on0, note_off0), (note_on1, note_off1), ...)
        """
        assert len(sequence) == len(keys)
        channels = itertools.cycle(self.available_channel)
        messages = []
        for tone, key in zip(sequence, keys):
            if not tone.pitch.is_empty:
                if tone.volume is not None:
                    typv = type(tone.volume)

                    if isinstance(tone.volume, numbers.Real):
                        volume = float(tone.volume)

                    elif isinstance(tone.volume, infit.InfIt):
                        volume = next(tone.volume)
                        try:
                            assert isinstance(volume, numbers.Real)
                        except AssertionError:
                            msg = "infit.InfIt object return bad type '{}'".format(
                                type(volume)
                            )
                            msg += " when trying to find a value for "
                            msg += "the volume argument."
                            raise ValueError(msg)

                    elif typv is interpolations.InterpolationLine:
                        volume = tone.volume(3, interpolation_type="points")[0]

                    else:
                        msg = "Unknown type '{}' for volume ".format(typv)
                        msg += "argument with the value '{}'".format(tone.volume)
                        raise NotImplementedError(msg)

                    velocity = int((volume / 1) * 127)
                else:
                    velocity = 64

                chnl = next(channels)
                msg0 = mido.Message(
                    "note_on", note=key, velocity=velocity, time=0, channel=chnl
                )
                msg1 = mido.Message(
                    "note_off", note=key, velocity=velocity, time=0, channel=chnl
                )
                messages.append((msg0, msg1))

        return tuple(messages)

    @staticmethod
    def detect_grid_position(sequence: tuple, grid: tuple, duration: float) -> tuple:
        def find_closest_point(points, time):
            pos = bisect.bisect_right(points, time)
            try:
                return min(
                    (
                        (abs(time - points[pos]), pos),
                        (abs(time - points[pos - 1]), pos - 1),
                    ),
                    key=operator.itemgetter(0),
                )[1]
            except IndexError:
                # if pos is len(points) + 1
                return pos - 1

        delays = tuple(float(tone.delay) for tone in sequence)
        starts = tuple(itertools.accumulate((0,) + delays))[:-1]
        durations = tuple(float(tone.duration) for tone in sequence)
        endings = tuple(s + d for s, d in zip(starts, durations))
        start_points = tuple(find_closest_point(grid, s) for s in starts)
        end_points = tuple(find_closest_point(grid, e) for e in endings)
        zipped = tuple(zip(start_points, end_points))
        return tuple(
            start_end
            for start_end, tone in zip(zipped, sequence)
            if not tone.pitch.is_empty
        )

    @property
    def sequence(self) -> tuple:
        return tuple(self.__sequence)

    def mk_control_messages_per_tone(
        self, sequence: tuple, n_points_per_tone: tuple
    ) -> tuple:
        channels = itertools.cycle(self.available_channel)
        return tuple(
            tone.control_messages(next(channels), n_points)
            for tone, n_points in zip(sequence, n_points_per_tone)
        )

    def mk_midi_track(self, messages: tuple) -> mido.MidiFile:
        mid = mido.MidiFile(type=0)
        bpm = 120
        ticks_per_minute = self.ticks_per_second * 60
        ticks_per_beat = int(ticks_per_minute / bpm)
        mid.ticks_per_beat = ticks_per_beat
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage("instrument_name", name="Acoustic Grand Piano"))

        for i in self.available_channel:
            track.append(mido.Message("program_change", program=0, time=0, channel=i))

        for message in messages:
            track.append(message)

        return mid

    @staticmethod
    def mk_overlapping_dict(sequence) -> dict:
        delays = tuple(float(t.delay) for t in sequence)
        absolute_delays = tuple(
            b - a for a, b in zip(delays, delays[1:] + (sum(delays),))
        )
        overlapping_dict = {i: [] for i, t in enumerate(sequence)}
        for i, tone in enumerate(sequence):
            if tone.delay < tone.duration:
                ending = delays[i] + tone.duration
                for j, abs_delay in enumerate(absolute_delays[i + 1 :]):
                    if abs_delay < ending:
                        overlapping_dict[i + j + 1].append(i)
                    else:
                        break
        return overlapping_dict

    @staticmethod
    def distribute_tones_on_midi_keys(
        sequence,
        amount_available_midi_notes,
        available_midi_notes,
        overlapping_dict,
        midi_keys_dict,
    ) -> tuple:
        def convert_keys(keys) -> tuple:
            return tuple(midi_keys_dict[t.pitch][key] for t, key in zip(sequence, keys))

        def is_alright(keys, overlapping_dict) -> bool:
            converted_keys = convert_keys(keys)
            for tone in tuple(overlapping_dict.keys())[: len(keys)]:
                simultan_tones = overlapping_dict[tone]
                current_keys = tuple(
                    converted_keys[idx] for idx in simultan_tones + [tone]
                )
                if len(current_keys) - len(set(current_keys)) != 0:
                    return False
            return True

        keys = [0]
        amount_tones = len(sequence)
        while len(keys) < amount_tones:
            if is_alright(keys, overlapping_dict) is True:
                keys.append(0)
            else:
                while keys[-1] + 1 == amount_available_midi_notes:
                    keys = keys[:-1]
                    if len(keys) == 0:
                        raise ValueError("No solution found! Too many simultan tones.")
                keys[-1] += 1
        converted_keys = convert_keys(keys)
        return tuple(available_midi_notes[key] for key in converted_keys)

    @staticmethod
    def mk_pitch_sequence(sequence: tuple) -> tuple:
        pitch_sequence = tuple(t.pitch for t in sequence)
        tuning_sequence = tuple(t.tuning for t in sequence)
        if sequence:
            pitches = set(
                functools.reduce(operator.add, tuning_sequence) + pitch_sequence
            )
        else:
            pitches = set([])
        midi_dict = MidiFile.mk_midi_pitch_dictionary(pitches)
        return pitch_sequence, tuning_sequence, midi_dict

    @staticmethod
    def mk_midi_pitch_dictionary(pitches: set) -> dict:
        return {
            pitch: pitch.convert2midi_tuning()
            for pitch in pitches
            if pitch != mel.TheEmptyPitch
        }

    @staticmethod
    def mk_midi_key_dictionary(
        pitches: set, available_midi_notes, amount_available_midi_notes
    ) -> dict:
        def evaluate_rating(pitch):
            freq = pitch.freq
            closest = bisect.bisect_right(available_frequencies, freq) - 1
            higher = tuple(range(closest + 1, amount_available_midi_notes))
            lower = tuple(range(closest - 1, -1, -1))
            ranking = (closest,) + tuple(
                functools.reduce(operator.add, zip(higher, lower))
            )
            len_h, len_l = len(higher), len(lower)
            if len_h > len_l:
                ranking += higher[len_l:]
            else:
                ranking += lower[len_h:]
            return ranking

        available_frequencies = tuple(_12edo_freq[idx] for idx in available_midi_notes)
        return {pitch: evaluate_rating(pitch) for pitch in pitches}

    def mk_complete_messages(
        self,
        filtered_sequence: tuple,
        gridsize: float,
        grid_position_per_tone: tuple,
        control_messages,
        note_on_off_messages,
        pitch_bending_per_channel,
        tuning_messages,
    ) -> tuple:
        length_seq = len(filtered_sequence)

        assert length_seq == len(control_messages)
        assert length_seq == len(note_on_off_messages)
        assert length_seq == len(tuning_messages)

        messages_per_tick = list(zip(*reversed(pitch_bending_per_channel)))
        messages_per_tick = [list(s) for s in messages_per_tick]

        for note_on_off, control_per_tick, tuning, grid_position in zip(
            note_on_off_messages,
            control_messages,
            tuning_messages,
            grid_position_per_tone,
        ):
            note_on, note_off = note_on_off
            start, stop = grid_position
            messages_per_tick[
                start + self.delay_between_control_messages_and_note_on_message
            ].append(note_on)
            messages_per_tick[start].extend(tuning)

            for position, c_msg in zip(range(start, stop), control_per_tick):
                messages_per_tick[position].extend(c_msg)

            messages_per_tick[
                stop + self.delay_between_control_messages_and_note_on_message
            ].append(note_off)
        messages_per_tick = tuple(tuple(reversed(tick)) for tick in messages_per_tick)
        return tuple(item for sublist in messages_per_tick for item in sublist)

    @property
    def miditrack(self) -> mido.MidiFile:
        return self.__miditrack

    def export(self, name: str = "test.mid") -> None:
        """save content of object to midi-file."""

        tuning_messages = self.mk_tuning_messages(
            self.__filtered_sequence,
            self.keys,
            self.__available_midi_notes,
            self.__overlapping_dict,
            self.__midi_pitch_dictionary,
        )

        messages = self.mk_complete_messages(
            self.__filtered_sequence,
            self.__gridsize,
            self.__grid_position_per_tone,
            self.__control_messages,
            self.__note_on_off_messages,
            self.__pitch_bending_per_channel,
            tuning_messages,
        )

        miditrack = self.mk_midi_track(messages)
        miditrack.save(name)


class SysexTuningMidiFile(MidiFile):
    """MidiFile for synthesizer that understand Sysex tuning messages."""

    def mk_tuning_messages(
        self, sequence, keys, available_midi_notes, overlapping_dict, midi_pitch_dict
    ) -> tuple:
        def check_for_available_midi_notes(
            available_midi_notes, overlapping_dict, keys, tone_index
        ) -> tuple:
            """Return tuple with two elements:

            1. midi_number for playing tone
            2. remaining available midi numbers for retuning
            """
            played_key = keys[tone_index]
            busy_keys = tuple(keys[idx] for idx in tuple(overlapping_dict[tone_index]))
            busy_keys += (played_key,)
            remaining_keys = tuple(
                key for key in available_midi_notes if key not in busy_keys
            )
            return (played_key, remaining_keys)

        def mk_tuning_messages_for_tone(tone, local_midi_notes) -> tuple:
            if tone.pitch != mel.TheEmptyPitch:
                midi_pitch = midi_pitch_dict[tone.pitch]
                played_midi_note, remaining_midi_notes = local_midi_notes
                tuning = tone.tuning
                if not tuning:
                    tuning = (tone.pitch,)
                tuning = list(tuning)
                amount_remaining_midi_notes = len(remaining_midi_notes)
                tuning_gen = itertools.cycle(tuning)
                while len(tuning) < amount_remaining_midi_notes:
                    tuning.append(next(tuning_gen))
                while len(tuning) > amount_remaining_midi_notes:
                    tuning = tuning[:-1]
                tuning = sorted(tuning)
                midi_tuning = tuple(midi_pitch_dict[pitch] for pitch in tuning)
                key_tuning_pairs = tuple(zip(sorted(remaining_midi_notes), midi_tuning))
                key_tuning_pairs = ((played_midi_note, midi_pitch),) + key_tuning_pairs
                messages = []
                for key, tuning in key_tuning_pairs:
                    msg = mido.Message(
                        "sysex",
                        data=(
                            127,
                            127,
                            8,
                            2,
                            0,
                            1,
                            key,
                            tuning[0],
                            tuning[1],
                            tuning[2],
                        ),
                        time=0,
                    )
                    messages.append(msg)
                return tuple(messages)
            else:
                return tuple([])

        available_midi_notes_per_tone = tuple(
            check_for_available_midi_notes(
                available_midi_notes, overlapping_dict, keys, i
            )
            for i in range(len(sequence))
        )
        tuning_messages_per_tone = tuple(
            mk_tuning_messages_for_tone(tone, local_midi_notes)
            for tone, local_midi_notes in zip(sequence, available_midi_notes_per_tone)
        )
        return tuning_messages_per_tone


class NonSysexTuningMidiFile(MidiFile):
    """MidiFile for synthesizer that can't understand Sysex tuning messages."""

    def mk_tuning_messages(
        self, sequence, keys, available_midi_notes, overlapping_dict, midi_pitch_dict
    ) -> tuple:
        """Make empty tuning messages."""
        tuning_messages_per_tone = tuple(tuple([]) for tone in zip(sequence))
        return tuning_messages_per_tone


class Pianoteq(SysexTuningMidiFile):
    software_path = "pianoteq"

    # somehow control messages take some time until they become valid in Pianoteq.
    # Therefore there has to be a delay between the last control change and
    # the next NoteOn - message.
    delay_between_control_messages_and_note_on_message = 40

    # for some weird reason pianoteq don't use channel 9
    available_channel = tuple(i for i in range(16) if i != 9)

    def __init__(
        self, sequence: tuple, available_midi_notes: tuple = tuple(range(128)), **kwargs
    ):
        super().__init__(sequence, available_midi_notes, **kwargs)

    def export2wav(
        self, name, nchnls=1, preset=None, fxp=None, sr=44100, verbose: bool = False
    ) -> subprocess.Popen:
        self.export("{0}.mid".format(name))
        cmd = [
            "{}".format(self.software_path),
            "--rate {}".format(sr),
            "--bit-depth 32",
            "--midimapping complete",
        ]

        if verbose is False:
            cmd.append("--quiet")

        if nchnls == 1:
            cmd.append("--mono")

        if preset is not None:
            cmd.append("--preset {}".format(preset))

        if fxp is not None:
            cmd.append("--fxp {} ".format(fxp))

        cmd.append("--midi {0}.mid --wav {0}.wav".format(name))
        return subprocess.Popen(" ".join(cmd), shell=True)


class Bliss(NonSysexTuningMidiFile):
    available_channel = (0,)  # only use one channel since it's monophonic anwyway

    def __init__(self, sequence: tuple, **kwargs):
        super().__init__(sequence, tuple(range(128), **kwargs))

    def detect_pitch_bending_per_tone(
        self, sequence, gridsize: float, grid_position_per_tone: tuple
    ) -> tuple:
        """Return tuple filled with tuples that contain cent deviation per step."""

        def mk_interpolation(obj, size):

            if obj:
                obj = list(obj.interpolate(gridsize))
            else:
                obj = []

            while len(obj) > size:
                obj = obj[:-1]

            while len(obj) < size:
                obj.append(0)

            return obj

        pitch_bending = []
        for tone, start_end in zip(sequence, grid_position_per_tone):
            size = start_end[1] - start_end[0]
            glissando = mk_interpolation(tone.glissando, size)
            vibrato = mk_interpolation(tone.vibrato, size)
            resulting_cents = tuple(a + b for a, b in zip(glissando, vibrato))
            pitch_bending.append(resulting_cents)

        return tuple(pitch_bending)


class Diva(NonSysexTuningMidiFile):
    available_channel = (0,)  # only use one channel since it's monophonic anwyway

    def __init__(self, sequence: tuple, **kwargs):
        super().__init__(sequence, tuple(range(128), **kwargs))

    def mk_control_messages_per_tone(
        self, sequence: tuple, n_points_per_tone: tuple
    ) -> tuple:
        channels = itertools.cycle(self.available_channel)
        return tuple(
            tone.control_messages(next(channels), n_points, key)
            for tone, n_points, key in zip(sequence, n_points_per_tone, self.keys)
        )

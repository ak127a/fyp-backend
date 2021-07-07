import time
from subprocess import run, call, PIPE

from flask import logging, Flask, render_template, request, Response, send_file


import pretty_midi
from note_seq import midi_io
from magenta.models.melody_rnn import melody_rnn_sequence_generator
from magenta.models.shared import sequence_generator_bundle
from note_seq.protobuf import generator_pb2
from note_seq.protobuf import music_pb2
from note_seq.midi_io import note_sequence_to_midi_file
from flask_cors import CORS, cross_origin


app = Flask(__name__, static_url_path='')
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/audio', methods=['POST'])
@cross_origin()
def audio():
    if request.method == 'POST':
        print("Recieved Audio File")
        file = request.files['file']
        print('File from the POST request is: {}'.format(file))
        with open("audio.wav", "wb") as aud:
            aud_stream = file.read()
            aud.write(aud_stream)
        result = call("audio-to-midi audio.wav -b 120 -t 900 -C 1")
        bundle = sequence_generator_bundle.read_bundle_file('./basic_rnn.mag')
        generator_map = melody_rnn_sequence_generator.get_generator_map()
        melody_rnn = generator_map['basic_rnn'](checkpoint=None, bundle=bundle)
        melody_rnn.initialize()

        # Read the mid file
        midi_data = pretty_midi.PrettyMIDI('audio.wav.mid')
        # convert into note sequence
        seq = midi_io.midi_to_note_sequence(midi_data)
        num_steps = 130  # change this for shorter or longer sequences
        # the higher the temperature the more random the sequence.
        temperature = 1.2

        input_sequence = seq

        # Set the start time to begin on the next step after the last note ends.
        last_end_time = (
            max(n.end_time for n in input_sequence.notes) if input_sequence.notes else 0)
        qpm = input_sequence.tempos[0].qpm
        seconds_per_step = 60.0 / qpm / melody_rnn.steps_per_quarter
        total_seconds = num_steps * seconds_per_step

        generator_options = generator_pb2.GeneratorOptions()
        generator_options.args['temperature'].float_value = temperature
        generate_section = generator_options.generate_sections.add(
            start_time=last_end_time + seconds_per_step, end_time=total_seconds)

        # Ask the model to continue the sequence.
        newseq = melody_rnn.generate(input_sequence, generator_options)

        # Convert the output sequence to midi
        print('line 67')
        note_sequence_to_midi_file(newseq, "output.mid")
        # os.popen('copy output.mid d:\fyp-frontend')
        # print('copy done')
    return "Success"


@app.route('/midfile')
def send_js():
    return send_file('output.mid')


# @app.route('/output')
# def send_mid():
#     return send_from_directory('/', 'output.mid')


@app.route("/wav")
def streamwav():
    def generate():
        with open("audio.wav", "rb") as fwav:
            print('inside the function')
            data = fwav.read(1024)
            while data:
                yield data
                data = fwav.read(1024)
    return Response(generate(), mimetype="audio/x-wav")


if __name__ == "__main__":
    app.logger = logging.getLogger('audio-gui')
    app.run(debug=True)

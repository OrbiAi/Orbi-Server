from flask import Blueprint, render_template, abort, request
import os
import sqlite3
import json
from db_utils import get_stats, get_captures, get_capture_info

frontend = Blueprint('frontend', __name__)

@frontend.route('/all')
def all_captures():
    total_captures, readable_size = get_stats()
    capture_list = get_captures()
    capture_list = [capture for capture in capture_list if capture['processed'] != 0]
    return render_template('all.html', total_captures=total_captures, total_size=readable_size, captures=capture_list)

@frontend.route('/info/<id>')
def capture_info(id):
    capture_dict = get_capture_info(id)
    if not capture_dict:
        abort(404)
    back_all = request.args.get('back') == 'all'
    if capture_dict['processed'] == 0:
        return render_template('processing.html', capture=capture_dict, back_all=back_all)
    return render_template('info.html', capture=capture_dict, back_all=back_all)
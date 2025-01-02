from flask import Blueprint, render_template, abort, request
import os
import json
from db_utils import get_stats, get_captures, get_capture_info

frontend = Blueprint('frontend', __name__)

@frontend.route('/all')
def all_captures():
    total_captures, processed_captures, readable_size = get_stats()
    capture_list = get_captures()
    capture_list = [capture for capture in capture_list if capture['processed'] != 0]
    per_page = 25 # TODO: make this changable via the web ui
    page = request.args.get('page', 1, type=int)
    total_pages = (len(capture_list) + per_page - 1) // per_page
    capture_list = capture_list[(page - 1) * per_page: page * per_page]
    return render_template('all.html', processed_captures=processed_captures, total_size=readable_size, captures=capture_list, page=page, total_pages=total_pages)

@frontend.route('/info/<id>')
def capture_info(id):
    capture_dict = get_capture_info(id)
    if not capture_dict:
        abort(404)
    back_all = request.args.get('back') == 'all'
    if capture_dict['processed'] == 0:
        return render_template('processing.html', capture=capture_dict, back_all=back_all)
    return render_template('info.html', capture=capture_dict, back_all=back_all)


from flask import Blueprint, render_template, abort, request
from db_utils import get_stats, get_captures, get_capture_info

frontend = Blueprint('frontend', __name__)

@frontend.route('/')
def homepage():
    # get stats
    total_captures, processed_captures, readable_size = get_stats()
    capture_list = get_captures(max=5, processed_only=True)
    # check for failed captures
    failed_captures = get_captures(failed_only=True)
    return render_template('homepage.html', processed_captures=processed_captures, total_size=readable_size, captures=capture_list, total_captures=total_captures, failed_captures=failed_captures)

@frontend.route('/all')
def all_captures():
    # get stats
    total_captures, processed_captures, readable_size = get_stats()
    capture_list = get_captures(processed_only=True)
    per_page = 25 # TODO: make this changable via the web ui
    # do pages
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

@frontend.route('/search')
def search():
    query = request.args.get('query', '')
    back_all = request.args.get('back') == 'all'
    capture_list = get_captures(search=query, processed_only=True)
    capture_amount = len(capture_list)
    per_page = 25 # TODO: make this changable via the web ui
    # do pages
    page = request.args.get('page', 1, type=int)
    total_pages = (len(capture_list) + per_page - 1) // per_page
    capture_list = capture_list[(page - 1) * per_page: page * per_page]
    return render_template('search.html', captures=capture_list, query=query, back_all=back_all, page=page, total_pages=total_pages, capture_amount=capture_amount)

@frontend.route('/failed_captures')
def failed_captures():
    # get stats
    failed_captures = get_captures(failed_only=True)
    per_page = 25 # TODO: make this changable via the web ui
    total_failed = len(failed_captures)
    # do pages
    page = request.args.get('page', 1, type=int)
    total_pages = (len(failed_captures) + per_page - 1) // per_page
    failed_captures = failed_captures[(page - 1) * per_page: page * per_page]
    return render_template('failed_captures.html', total_failed=total_failed, failed_captures=failed_captures, page=page, total_pages=total_pages)
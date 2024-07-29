use c2d_lexer::C2DToken;
use clap::Parser;
use ddnnife::parser::c2d_lexer;
use std::collections::HashMap;
use std::fs::File;
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::time::Instant;

#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

#[derive(Parser)]
#[command(version, arg_required_else_help(true))]
struct Cli {
    /// The input file must be generated by dsharp with the smoothing flag set to true
    file_path: String,

    /// Sets a custom output file
    #[arg(short, long, value_name = "FILE", default_value_t = String::from("preprocessed.nnf"))]
    save_as: String,
}

/// For some reason dsharp is not able to smooth a d-dnnf while still satisfy
/// the standard. Therefore, we have to adjust the resulting d-dnnf to enforce all rules.
/// dsharp violates the standard by generating two instances of the same literal for some
/// literals. We can resolve that issue by replacing the first occurence with a dummy value.
/// The dummy ensures the validity of the counting algorithm for other literals and configurations
/// that do not contain the doubled literal. We choose a true node as dummy.

fn main() {
    let cli = Cli::parse();

    let time = Instant::now();

    let token_stream = preprocess(&cli.file_path);

    let file: File = File::create(cli.save_as).expect("Unable to create file");
    let mut buf_writer = BufWriter::new(file);

    for token in token_stream {
        buf_writer
            .write_all(c2d_lexer::deconstruct_C2DToken(token).as_bytes())
            .expect("Unable to write data");
    }

    let elapsed_time = time.elapsed().as_secs_f32();
    println!(
        "Elapsed time for preprocessing {}: {:.3}s.",
        cli.file_path, elapsed_time
    );
}

#[inline]
/// Preprocesses a ddnnf and replaces duplicates of literals (if occuring)
/// with true nodes. There the first occurence always stays the same and all other
/// occurences are swaped with dummy values. We choose true nodes because they do not change
/// the endresult in any way
/// # Examples
///
/// ```
/// extern crate ddnnf_lib;
/// use ddnnf_lib::parser;
///
/// let file_path = "./tests/data/small_test.dimacs.nnf";
/// preprocess(file_path);
/// ```
///
/// # Panics
///
/// The function panics for an invalid file path.
fn preprocess(path: &str) -> Vec<C2DToken> {
    let mut token_stream: Vec<C2DToken> = get_token_stream(path);

    let mut literals: HashMap<i32, usize> = HashMap::new();

    // indices of nodes that should be replaced with true nodes
    let mut changes: Vec<usize> = Vec::new();

    for (index, token) in token_stream.iter().enumerate() {
        // if we find a literal we save the number and its position
        let unique: i32 = match token {
            C2DToken::Literal { feature: f } => {
                if literals.contains_key(f) {
                    *f
                } else {
                    literals.insert(*f, index);
                    0
                }
            }
            _ => 0,
        };

        // if the literal already exists in a previous line then we replace all further
        // occurences with a true node
        if unique != 0 {
            let pos: usize = *literals.get(&unique).unwrap();
            changes.push(pos);
        }
    }

    for change in changes {
        token_stream[change] = C2DToken::True;
    }
    token_stream
}

// generates a token stream from a file path
fn get_token_stream(path: &str) -> Vec<C2DToken> {
    let file = File::open(path).unwrap();
    let lines = BufReader::new(file)
        .lines()
        .map(|line| line.expect("Unable to read line"));
    // we do not know the capacity beforehand without applying semmantics but we know that the file will often be quite big
    let mut parsed_tokens: Vec<C2DToken> = Vec::with_capacity(10000);

    // opens the file with a BufReader and
    // works off each line of the file data seperatly
    for line in lines {
        parsed_tokens.push(c2d_lexer::lex_line_c2d(line.as_ref()).unwrap().1);
    }

    parsed_tokens
}